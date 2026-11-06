import gzip
import json
import os
import time
import uuid
from datetime import datetime
from typing import Type

import dill as pickle
from pydantic import BaseModel
from rich.pretty import pretty_repr

from core.event import EventDispatcher, EventSystemCloseEvent
from core.log import get_clearml, get_logger, is_enabled_clearml
from core.utils import get_frame

from .prompts.base import PromptBase
from .utils import MODEL_REGISTRY, clean_llm_response, save_api_history


def register_model(cls):
    """Decorator to register a pydantic model using its fully qualified name."""
    MODEL_REGISTRY[cls.__qualname__] = cls
    return cls


def save_json_compressed(data, filename):
    """
    Save data to a compressed JSON file.
    Data structure is a list of dictionaries with keys:
    - "model": str
    - "prompt": dict
    - "response": dict
    - "parsed_response": dict
    For the "response" field, record the registered model's fully qualified name and its dumped data.
    """
    new_data = []
    for item in data:
        new_item = dict(item)
        response = item.get("parsed_response")
        if isinstance(response, BaseModel):
            model_qualname = response.__class__.__qualname__
            # Check if the model is registered using its qualified name
            if model_qualname not in MODEL_REGISTRY:
                raise ValueError(f"Model {model_qualname} is not registered")
            new_item["parsed_response"] = {
                "__model__": model_qualname,
                "data": response.model_dump(),
            }
        new_data.append(new_item)
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2)


def load_json_compressed(filename):
    """
    Load data from a compressed JSON file.
    For the "response" field, automatically deserialize the object by:
      - Looking up the registered model using the "__model__" key (which is the fully qualified name).
      - Using parse_obj() to recreate the pydantic model instance.
    """
    with gzip.open(filename, "rt", encoding="utf-8") as f:
        loaded_data = json.load(f)
    new_data = []
    for item in loaded_data:
        new_item = dict(item)
        response = item.get("parsed_response")
        if (
            isinstance(response, dict)
            and "__model__" in response
            and "data" in response
        ):
            model_qualname = response["__model__"]
            if model_qualname not in MODEL_REGISTRY:
                raise ValueError(f"Model {model_qualname} is not registered")
            model_cls = MODEL_REGISTRY[model_qualname]
            new_item["parsed_response"] = model_cls.parse_obj(response["data"])
        new_data.append(new_item)
    return new_data


class LLMAPI(EventDispatcher):
    RETRY = -1

    def __init__(self, retry=-1, **kwargs):
        self._logger = get_logger()
        self.RETRY = retry
        self._query_kwargs = kwargs
        self._history = []
        self._prompts = {}  # {hash: prompt} for deduplication

    def query(
        self,
        model: str,
        prompt: dict,
        prompt_cls: Type[PromptBase],
        api_key: str = None,
        base_url: str = None,
        use_langfuse: bool = False,
        **kwargs,
    ) -> PromptBase.Response:
        try:
            if use_langfuse:
                from langfuse.openai import OpenAI
            else:
                from openai import OpenAI
        except ImportError:
            from openai import OpenAI
        _kwargs = self._query_kwargs.copy()
        _kwargs.update(kwargs)

        # Only pass langfuse-specific parameters if using langfuse
        # Standard OpenAI API doesn't accept session_id or tags parameters
        if use_langfuse:
            _kwargs["tags"] = [model] + _kwargs.pop("tags", [])
        else:
            _kwargs.pop("session_id", None)
            _kwargs.pop("tags", None)
        retry = self.RETRY
        completion = None
        parsed_resp = None
        last_exc = None
        while retry > 0 or self.RETRY == -1:
            try:
                self._logger.debug(f"Querying model: {model} with kwargs: {_kwargs}")
                completion = OpenAI(
                    api_key=api_key, base_url=base_url
                ).chat.completions.create(
                    model=model,
                    messages=prompt,
                    **_kwargs,
                )
                self._logger.debug(f"Response: {pretty_repr(completion)}")
                # Clean LLM response to remove special token markers
                raw_content = completion.choices[0].message.content
                cleaned_content = clean_llm_response(raw_content)
                parsed_resp = prompt_cls.parse_response(cleaned_content)
                self._history.append(
                    {
                        "model": model,
                        "prompt": prompt,
                        "kwargs": _kwargs,
                        "response": completion.to_dict(),
                        "parsed_response": parsed_resp,
                    }
                )
                break
            except Exception as e:
                last_exc = e
                self._logger.error("Error when query", exc_info=True)
                retry -= 1

                # Save failed request if retry count exceeds 3 (only save once)
                current_retry_count = self.RETRY - retry
                if current_retry_count == 4:  # Save only when it hits exactly 4 retries
                    self._save_failed_request(
                        model, prompt, _kwargs, e, current_retry_count, completion
                    )

                self._logger.debug(f"Retrying in {current_retry_count} seconds...")
                time.sleep(current_retry_count)
            except KeyboardInterrupt:
                self._logger.error("KeyboardInterrupt", exc_info=True)
                raise
        if parsed_resp is None:
            # Finite-retry path exhausted all attempts (RETRY=-1 only exits via break/KeyboardInterrupt,
            # so parsed_resp is always set there). Raise a clean, chainable RuntimeError (not an
            # UnboundLocalError on parsed_resp) so callers can inspect the underlying cause via the
            # __cause__ chain.
            raise RuntimeError(
                f"LLMAPI.query failed after {self.RETRY} attempts for model {model}"
            ) from last_exc
        return parsed_resp

    def save_history(self):
        filename = f"{self.__class__.__name__}_api_history.json.gz"
        filepath = f"{self._logger.log_path}/{filename}"
        save_api_history(self._history, filepath)
        self._logger.debug(f"History saved to {filepath}")
        if is_enabled_clearml():
            task = get_clearml()
            task.upload_artifact(
                name=filename,
                artifact_object=filepath,
                metadata={"description": "LLM API history"},
            )

        return self._history

    def _save_failed_request(
        self, model, prompt, kwargs, exception, retry_count, completion=None
    ):
        """Save failed request data for later reproduction"""
        try:
            # Create failed requests directory
            failed_requests_dir = os.path.join(self._logger.log_path, "failed_requests")
            os.makedirs(failed_requests_dir, exist_ok=True)

            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            request_id = str(uuid.uuid4())[:8]
            filename = f"failed_request_{timestamp}_{request_id}.json"
            filepath = os.path.join(failed_requests_dir, filename)

            # Prepare request data for saving
            failed_request_data = {
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                "model": model,
                "prompt": prompt,
                "kwargs": kwargs,
                "retry_count": retry_count,
                "error": {
                    "type": type(exception).__name__,
                    "message": str(exception),
                    "args": exception.args if hasattr(exception, "args") else [],
                },
            }

            # Save completion if available and has content
            if (
                completion
                and hasattr(completion, "choices")
                and len(completion.choices) > 0
                and hasattr(completion.choices[0], "message")
                and hasattr(completion.choices[0].message, "content")
            ):
                failed_request_data["completion"] = completion.to_dict()

            # Save to JSON file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(failed_request_data, f, indent=2, ensure_ascii=False)

            self._logger.warning(f"Failed request saved to: {filepath}")

        except Exception as save_error:
            self._logger.error(
                f"Failed to save error request: {save_error}", exc_info=True
            )

    @EventDispatcher.on(EventSystemCloseEvent)
    def close(self):
        self._logger.debug("Closing LLMAPI")
        self.save_history()
