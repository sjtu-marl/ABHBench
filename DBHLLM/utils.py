import base64
import copy
import gzip
import hashlib
import io
import json
import os
import re
from typing import Any, Dict, List, Tuple

import pandas as pd
from PIL import Image
from pydantic import BaseModel

# Global registry for registered models using fully qualified names
MODEL_REGISTRY: Dict[str, type] = {}

# Pattern to match HTML comments (used for random hash)
_COMMENT_PATTERN = re.compile(r'<!--.*?-->\n?')


def _serialize_value(value: Any) -> Any:
    """Convert Pydantic models to dicts for JSON serialization."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


def _clean_prompt_for_hash(prompt: list) -> list:
    """Remove random hash comments from prompt for deduplication."""
    def clean_content(content):
        if isinstance(content, str):
            return _COMMENT_PATTERN.sub('', content)
        if isinstance(content, dict):
            return {k: clean_content(v) for k, v in content.items()}
        if isinstance(content, list):
            return [clean_content(item) for item in content]
        return content
    return clean_content(prompt)


def _hash_prompt(prompt: list) -> str:
    """Generate a hash for a prompt, ignoring random hash comments."""
    return hashlib.md5(json.dumps(_clean_prompt_for_hash(prompt), sort_keys=True).encode()).hexdigest()[:12]


def _extract_random_hash(prompt: list) -> str:
    """Extract random hash from prompt if present."""
    if not prompt:
        return None
    first_content = prompt[0].get("content")
    if isinstance(first_content, str):
        match = re.match(r'<!--\s*(\S+)\s*-->', first_content)
        return match.group(1) if match else None
    if isinstance(first_content, list):
        for item in first_content:
            if item.get("type") == "text":
                match = re.match(r'<!--\s*(\S+)\s*-->', item.get("text", ""))
                return match.group(1) if match else None
    return None


def _restore_random_hash(prompt: list, random_hash: str) -> list:
    """Restore random hash to prompt."""
    if not prompt or not random_hash:
        return prompt
    prompt = copy.deepcopy(prompt)
    first_content = prompt[0].get("content")
    if isinstance(first_content, str):
        prompt[0]["content"] = f"<!-- {random_hash} -->\n{first_content}"
    elif isinstance(first_content, list):
        for item in first_content:
            if item.get("type") == "text":
                item["text"] = f"<!-- {random_hash} -->\n{item['text']}"
                break
    return prompt


def save_api_history(history: List[Dict], filepath: str) -> None:
    """Save API history with deduplicated prompts."""
    prompts = {}
    data = []
    for item in history:
        prompt = item.get("prompt")
        prompt_hash = _hash_prompt(prompt)
        if prompt_hash not in prompts:
            prompts[prompt_hash] = _clean_prompt_for_hash(prompt)
        new_item = {k: v for k, v in item.items() if k != "prompt"}
        new_item["prompt_hash"] = prompt_hash
        random_hash = _extract_random_hash(prompt)
        if random_hash:
            new_item["random_hash"] = random_hash
        # Handle parsed_response Pydantic models
        parsed_response = item.get("parsed_response")
        if isinstance(parsed_response, BaseModel):
            model_qualname = parsed_response.__class__.__qualname__
            if model_qualname not in MODEL_REGISTRY:
                raise ValueError(f"Model {model_qualname} is not registered")
            new_item["parsed_response"] = {
                "__model__": model_qualname,
                "data": parsed_response.model_dump(),
            }
        data.append(new_item)
    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        json.dump({"prompts": prompts, "data": data}, f, indent=2)


def load_api_history(filepath: str) -> List[Dict]:
    """Load API history and restore prompts."""
    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    if "prompts" in raw and "data" in raw:
        prompts = raw["prompts"]
        history = []
        for item in raw["data"]:
            prompt_hash = item.pop("prompt_hash", None)
            random_hash = item.pop("random_hash", None)
            base_prompt = prompts.get(prompt_hash) if prompt_hash else None
            item["prompt"] = _restore_random_hash(base_prompt, random_hash) if random_hash else base_prompt
            # Restore parsed_response Pydantic models
            parsed_response = item.get("parsed_response")
            if (
                isinstance(parsed_response, dict)
                and "__model__" in parsed_response
                and "data" in parsed_response
            ):
                model_qualname = parsed_response["__model__"]
                if model_qualname not in MODEL_REGISTRY:
                    raise ValueError(f"Model {model_qualname} is not registered")
                model_cls = MODEL_REGISTRY[model_qualname]
                item["parsed_response"] = model_cls.model_validate(parsed_response["data"])
            history.append(item)
        return history
    return raw


def save_choices_history(choices_history: Dict, filepath: str) -> None:
    """Save choices history with deduplicated prompts."""
    prompts = {}
    data = {}
    for key, iterations in choices_history.items():
        new_iterations = []
        for iteration in iterations:
            new_iteration = {k: v for k, v in iteration.items() if k != "choices_pair"}
            new_choices_pair = []
            for pair in iteration.get("choices_pair", []):
                prompt = pair.get("prompt")
                prompt_hash = _hash_prompt(prompt)
                if prompt_hash not in prompts:
                    prompts[prompt_hash] = _clean_prompt_for_hash(prompt)
                new_pair = {k: _serialize_value(v) for k, v in pair.items() if k not in ("prompt", "random_hash")}
                new_pair["prompt_hash"] = prompt_hash
                random_hash = _extract_random_hash(prompt)
                if random_hash:
                    new_pair["random_hash"] = random_hash
                new_choices_pair.append(new_pair)
            new_iteration["choices_pair"] = new_choices_pair
            new_iterations.append(new_iteration)
        data[key] = new_iterations
    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        json.dump({"prompts": prompts, "data": data}, f, indent=2)


def load_choices_history(filepath: str) -> Dict:
    """Load choices history, compatible with both old and new formats."""
    with gzip.open(filepath, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    if "prompts" not in raw or "data" not in raw:
        return raw  # Old format
    prompts = raw["prompts"]
    choices_history = {}
    for key, iterations in raw["data"].items():
        new_iterations = []
        for iteration in iterations:
            new_iteration = {k: v for k, v in iteration.items() if k != "choices_pair"}
            new_choices_pair = []
            for pair in iteration.get("choices_pair", []):
                prompt_hash = pair.pop("prompt_hash", None)
                random_hash = pair.get("random_hash")
                base_prompt = prompts.get(prompt_hash) if prompt_hash else None
                pair["prompt"] = _restore_random_hash(base_prompt, random_hash) if random_hash else base_prompt
                new_choices_pair.append(pair)
            new_iteration["choices_pair"] = new_choices_pair
            new_iterations.append(new_iteration)
        choices_history[key] = new_iterations
    return choices_history


def mfts(
    input_data: str | list | pd.DataFrame,
    dict_type: str,
    prob_map: dict,
    score_method: str,
    out_metrics: list,
) -> pd.DataFrame:
    """
    Process the input data and compute scores.

    Parameters:
    input_data (str | list | pd.DataFrame): The input data to be processed. It can be a single string,
                                            a list of strings, or a pandas DataFrame.

    Returns:
    pd.DataFrame: A DataFrame containing the computed scores.

    Raises:
    ValueError: If the input data is not a string, a list of strings, or a pandas DataFrame.
    """
    from emfdscore.scoring import score_docs

    if isinstance(input_data, str):
        input_data = pd.DataFrame([input_data])
    elif isinstance(input_data, list):
        input_data = pd.DataFrame(input_data)
    elif not isinstance(input_data, pd.DataFrame):
        raise ValueError(
            "Input data must be a string, a list of strings, or a pandas DataFrame"
        )

    scores = score_docs(
        input_data, dict_type, prob_map, score_method, out_metrics, len(input_data)
    )
    return scores


def combine_images(
    images: List[Image.Image],
    layout: Tuple[int, int],
    width: int = None,
    height: int = None,
):
    """
    Combine a list of PIL.Image objects into one image based on the specified layout.

    Parameters:
        images: A list of PIL.Image objects.
        layout: A tuple (rows, cols) where, for example, (1, 2) means 1 row and 2 columns.
        width: The target width of the output image. Default is None.
        height: The target height of the output image. Default is None.

    Returns:
        A combined PIL.Image object.
    """
    rows, cols = layout
    if len(images) != rows * cols:
        raise ValueError("The number of images does not match the layout (rows * cols)")

    # Group the images by rows
    grid = [images[i * cols : (i + 1) * cols] for i in range(rows)]

    # Calculate the maximum width for each column
    col_widths = []
    for j in range(cols):
        max_width = max(grid[i][j].width for i in range(rows))
        col_widths.append(max_width)

    # Calculate the maximum height for each row
    row_heights = []
    for i in range(rows):
        max_height = max(img.height for img in grid[i])
        row_heights.append(max_height)

    # Calculate the total size of the combined image
    total_width = sum(col_widths)
    total_height = sum(row_heights)

    # Create a new image with a white background (can be adjusted as needed)
    new_img = Image.new("RGB", (total_width, total_height), color=(255, 255, 255))

    # Paste the images into the new image in order from left to right and top to bottom
    y_offset = 0
    for i in range(rows):
        x_offset = 0
        for j in range(cols):
            img = grid[i][j]
            new_img.paste(img, (x_offset, y_offset))
            x_offset += col_widths[j]
        y_offset += row_heights[i]

    # If width or height is specified, scale the image proportionally
    if width is not None or height is not None:
        orig_width, orig_height = new_img.size
        if width is not None and height is None:
            scale_factor = width / orig_width
        elif height is not None and width is None:
            scale_factor = height / orig_height
        else:
            scale_factor = min(width / orig_width, height / orig_height)

        new_size = (int(orig_width * scale_factor), int(orig_height * scale_factor))
        new_img = new_img.resize(new_size, Image.Resampling.LANCZOS)

    return new_img


class ImageMetadata:
    """Container for image and associated metadata"""

    def __init__(self, image: Image.Image, context: str = None, act: str = None):
        self.image = image
        self.context = context
        self.act = act


class ImageQueueCombiner:
    def __init__(self, layout: Tuple[int, int], width: int = None, height: int = None):
        """
        Initialize the combiner with a layout and optional width and height for scaling.

        Parameters:
            layout (tuple): A tuple (rows, cols) indicating the grid layout.
            width (int, optional): The target width of the combined image.
            height (int, optional): The target height of the combined image.
        """
        self.layout = layout
        self.width = width
        self.height = height
        self.rows, self.cols = layout
        self.capacity = self.rows * self.cols
        self.queue = []  # Now stores ImageMetadata objects

    def add_image(self, image: Image.Image, context: str = None, act: str = None):
        """
        Add an image with metadata to the FIFO queue.

        If this is the first image, fill the entire queue with it.
        If the queue is not full, simply append the new image.
        Once full, perform FIFO replacement (remove the oldest and append the new image).

        Parameters:
            image (PIL.Image): The image to add.
            context (str, optional): The context associated with this image.
            act (str, optional): The action associated with this image.
        """
        metadata = ImageMetadata(image, context, act)

        if not self.queue:
            # For the first image, fill the entire queue with this image metadata.
            self.queue = [metadata] * self.capacity
        elif len(self.queue) < self.capacity:
            self.queue.append(metadata)
        else:
            self.queue.pop(0)
            self.queue.append(metadata)

    def get_combined_image(self):
        """
        Combine the images in the queue according to the layout and return the combined image.

        If the queue does not have enough images, fill missing slots by repeating the first image.
        The images are arranged in a grid (left-to-right, top-to-bottom). If width or height is
        specified, the final image is scaled proportionally.

        Returns:
            PIL.Image: The combined image.
        """
        if not self.queue:
            raise ValueError("Queue is empty, cannot combine images.")

        # Extract images from metadata
        images = [metadata.image for metadata in self.queue]

        # If the queue is not full, fill missing slots with the first image.
        if len(images) < self.capacity:
            images_to_combine = [images[0]] * (self.capacity - len(images)) + images
        else:
            images_to_combine = images

        # Arrange the images into a grid (row-major order)
        grid = [
            images_to_combine[i * self.cols : (i + 1) * self.cols]
            for i in range(self.rows)
        ]

        # Calculate the maximum width for each column
        col_widths = []
        for j in range(self.cols):
            max_width = max(grid[i][j].width for i in range(self.rows))
            col_widths.append(max_width)

        # Calculate the maximum height for each row
        row_heights = []
        for i in range(self.rows):
            max_height = max(img.height for img in grid[i])
            row_heights.append(max_height)

        # Calculate the total size of the combined image
        total_width = sum(col_widths)
        total_height = sum(row_heights)

        # Create a new image with a white background
        new_img = Image.new("RGB", (total_width, total_height), color=(255, 255, 255))

        # Paste each image into the new image in order from left-to-right and top-to-bottom
        y_offset = 0
        for i in range(self.rows):
            x_offset = 0
            for j in range(self.cols):
                new_img.paste(grid[i][j], (x_offset, y_offset))
                x_offset += col_widths[j]
            y_offset += row_heights[i]

        # If width or height is specified, scale the image proportionally
        if self.width is not None or self.height is not None:
            orig_width, orig_height = new_img.size
            if self.width is not None and self.height is None:
                scale_factor = self.width / orig_width
            elif self.height is not None and self.width is None:
                scale_factor = self.height / orig_height
            else:
                scale_factor = min(self.width / orig_width, self.height / orig_height)

            new_size = (int(orig_width * scale_factor), int(orig_height * scale_factor))

            # Use the appropriate resampling filter based on the Pillow version
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.LANCZOS
            new_img = new_img.resize(new_size, resample=resample_filter)

        return new_img

    def get_queue_metadata(self):
        """
        Get all metadata from the queue.

        Returns:
            List[ImageMetadata]: List of metadata objects in the queue.
        """
        return self.queue.copy()

    def get_latest_metadata(self):
        """
        Get the metadata of the most recently added image.

        Returns:
            ImageMetadata: The most recent metadata object, or None if queue is empty.
        """
        if not self.queue:
            return None
        return self.queue[-1]


# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def encode_image_pillow(image: Image.Image, format="jpeg"):
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str


def get_llm_kwargs(model: str) -> Dict:
    """
    Load LLM parameters from environment variables for the specified model.

    Parameters:
        model (str): The model identifier to load parameters for.

    Returns:
        Dict: A dictionary with the LLM parameters.
    """
    extra_params = json.loads(os.getenv("LLMs.extra_params", "{}"))
    model_extra_params = json.loads(os.getenv(f"LLMs.{model}.extra_params", "{}"))
    extra_params.update(model_extra_params)

    llm_kwargs = {
        "model": os.getenv(f"LLMs.{model}.model"),
        "base_url": os.getenv(f"LLMs.{model}.base_url"),
        "api_key": os.getenv(f"LLMs.{model}.api_key"),
        **extra_params,
    }

    return llm_kwargs


def clean_llm_response(response: str) -> str:
    """
    Clean LLM response by removing special token markers that may appear in model outputs.

    This function removes common token markers like <|begin_of_box|> and <|end_of_box|>
    that some language models include in their responses.

    Parameters:
        response (str): The raw response from the language model.

    Returns:
        str: The cleaned response with token markers removed.
    """
    if not isinstance(response, str):
        return response

    # Remove <|begin_of_box|> and <|end_of_box|> markers
    cleaned = response.replace("<|begin_of_box|>", "").replace("<|end_of_box|>", "")

    # Strip any resulting whitespace
    return cleaned.strip()
