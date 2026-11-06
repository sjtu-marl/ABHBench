import base64
import os
import os.path
import time

import pytest
from dotenv import load_dotenv
from langfuse.decorators import observe
from langfuse.openai import OpenAI, openai

load_dotenv()


def encode_image_base64(image_path):
    """Encode an image file as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@observe()
def test_openai_create():
    """Test direct call to OpenAI's chat completions create method."""
    # Get environment variables
    api_key = os.getenv("LITELLM_API_KEY")
    base_url = os.getenv("LITELLM_API_URL")
    model = os.getenv("LITELLM_MODEL")  # Get model from environment variables

    # Ensure we have the necessary environment variables
    assert api_key is not None, "LITELLM_API_KEY environment variable is required"
    assert base_url is not None, "LITELLM_API_URL environment variable is required"
    assert model is not None, "LITELLM_MODEL environment variable is required"

    # Create OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # Test data
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, please reply with a short greeting."},
    ]

    # Make the API call with retry logic
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Make the API call
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
            )

            # Assert that we got a valid response
            assert completion is not None
            assert hasattr(completion, "choices")
            assert len(completion.choices) > 0
            assert hasattr(completion.choices[0], "message")
            assert hasattr(completion.choices[0].message, "content")

            # Print the response content
            response_content = completion.choices[0].message.content
            print(f"Response: {response_content}")

            # Test passed
            break

        except Exception as e:
            print(f"Attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            time.sleep(retry_count)  # Increasing backoff

            # If we've exhausted all retries, fail the test
            if retry_count >= max_retries:
                pytest.fail(f"API call failed after {max_retries} attempts: {str(e)}")
    openai.flush_langfuse()


@observe()
def test_openai_create_with_image():
    """Test OpenAI's chat completions with image input."""
    # Get environment variables
    api_key = os.getenv("LITELLM_API_KEY")
    base_url = os.getenv("LITELLM_API_URL")
    model = os.getenv("LITELLM_MODEL")  # Get model from environment variables

    # Ensure we have the necessary environment variables
    assert api_key is not None, "LITELLM_API_KEY environment variable is required"
    assert base_url is not None, "LITELLM_API_URL environment variable is required"
    assert model is not None, "LITELLM_MODEL environment variable is required"

    # Create OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # Get an image path from tests/data
    image_path = os.path.join(
        "tests", "data", "Raw Screenshot_raw screenshot_00000064.jpeg"
    )
    assert os.path.exists(image_path), f"Image not found at {image_path}"

    # Encode the image
    base64_image = encode_image_base64(image_path)

    # Test data with image
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that can analyze images.",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What's in this image? Please describe it briefly.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        },
    ]

    # Make the API call with retry logic
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Make the API call
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
            )

            # Assert that we got a valid response
            assert completion is not None
            assert hasattr(completion, "choices")
            assert len(completion.choices) > 0
            assert hasattr(completion.choices[0], "message")
            assert hasattr(completion.choices[0].message, "content")

            # Print the response content
            response_content = completion.choices[0].message.content
            print(f"Image Analysis Response: {response_content}")

            # Test passed
            break

        except Exception as e:
            print(f"Attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            time.sleep(retry_count)  # Increasing backoff

            # If we've exhausted all retries, fail the test
            if retry_count >= max_retries:
                pytest.fail(f"API call failed after {max_retries} attempts: {str(e)}")
    openai.flush_langfuse()
