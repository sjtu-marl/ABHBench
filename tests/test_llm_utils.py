import os

from PIL import Image

from DBHLLM.utils import ImageQueueCombiner


def test_image_queue_combiner():
    # Read test images from data directory
    test_images = []
    try:
        # Find all available test images that match the pattern instead of hard-coding indices
        image_dir = os.path.join("tests", "data")
        image_pattern = r"Raw Screenshot_raw screenshot_(\d{8})\.jpeg"

        # Get all matching image files and sort them by index
        image_files = []
        for filename in os.listdir(image_dir):
            import re

            match = re.match(image_pattern, filename)
            if match:
                index = int(match.group(1))
                image_files.append((index, os.path.join(image_dir, filename)))

        # Sort by index and take the first 4 images (or fewer if not enough available)
        image_files.sort()
        image_files = image_files[:4]  # Limit to 4 images as needed by the test

        # Load the images with proper resource management
        for _, img_path in image_files:
            with Image.open(img_path) as img:
                # Create a copy to avoid issues after file is closed
                test_images.append(img.copy())

        # Ensure we have enough images for the test
        if len(test_images) < 4:
            raise ValueError(
                f"Not enough test images found. Found {len(test_images)}, need at least 4."
            )

    except (FileNotFoundError, OSError) as e:
        raise RuntimeError(f"Error loading test images: {e}")

    # Create a 2x2 image combiner
    combiner = ImageQueueCombiner(layout=(2, 2))

    # Verify the combiner is initialized with correct attributes
    assert combiner.rows == 2
    assert combiner.cols == 2
    assert combiner.capacity == 4
    assert len(combiner.queue) == 0

    # Add first image and verify queue is filled with it
    combiner.add_image(test_images[0])
    assert len(combiner.queue) == 4
    for img in combiner.queue:
        assert img.image == test_images[0]

    # Add second image and verify it's appended to the queue
    combiner.add_image(test_images[1])
    assert len(combiner.queue) == 4
    assert combiner.queue[0].image == test_images[0]
    assert combiner.queue[1].image == test_images[0]
    assert combiner.queue[2].image == test_images[0]
    assert combiner.queue[3].image == test_images[1]

    # Add remaining images and verify FIFO behavior
    combiner.add_image(test_images[2])
    combiner.add_image(test_images[3])
    assert len(combiner.queue) == 4
    assert combiner.queue[0].image == test_images[0]
    assert combiner.queue[1].image == test_images[1]
    assert combiner.queue[2].image == test_images[2]
    assert combiner.queue[3].image == test_images[3]

    combined_img = combiner.get_combined_image()

    # Add one more image to verify FIFO replacement (oldest removed)
    combiner.add_image(test_images[0])
    assert len(combiner.queue) == 4
    assert combiner.queue[0].image == test_images[1]
    assert combiner.queue[1].image == test_images[2]
    assert combiner.queue[2].image == test_images[3]
    assert combiner.queue[3].image == test_images[0]

    # Get combined image and verify it's a valid PIL Image
    combined_img = combiner.get_combined_image()
    assert isinstance(combined_img, Image.Image)

    # Test with width/height specified
    combiner_with_size = ImageQueueCombiner(layout=(2, 2), width=800, height=600)
    for img in test_images:
        combiner_with_size.add_image(img)
    resized_img = combiner_with_size.get_combined_image()

    # Verify the resized dimensions don't exceed the specified width/height
    assert resized_img.width <= 800
    assert resized_img.height <= 600
