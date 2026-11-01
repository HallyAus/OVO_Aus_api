"""Exercise actual Home Assistant image code against the Pillow security backport."""

from importlib.metadata import version
from io import BytesIO

import pytest
from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from homeassistant import const as ha_const
from homeassistant.components.image_upload import _generate_thumbnail_if_file_does_not_exist
from homeassistant.util.pil import draw_box
from packaging.version import Version
from PIL import Image, ImageDraw


def test_runtime_loads_the_patched_pillow_version():
    assert Version(version("Pillow")) >= Version("13.0.0")


def test_backport_identity_preserves_home_assistant_version_comparisons():
    """A package build label must not break HA's calendar-version comparisons."""
    assert version("homeassistant") == "2026.10.4+ovo.pillow13.1"
    assert ha_const.SECURITY_BACKPORT == "ovo.pillow13.1"
    assert ha_const.__version__ == "2026.10.4"
    runtime = AwesomeVersion(ha_const.__version__)
    assert runtime.strategy == AwesomeVersionStrategy.CALVER
    assert runtime == AwesomeVersion("2026.10.4")
    assert runtime >= AwesomeVersion("2026.10.4")
    assert runtime > AwesomeVersion("2026.10.3")
    assert runtime < AwesomeVersion("2026.10.5")


@pytest.mark.parametrize(("mode", "input_format", "content_type", "output_mode"), [
    ("RGB", "JPEG", "image/jpeg", "RGB"),
    ("RGBA", "PNG", "image/jpeg", "RGB"),
    ("LA", "PNG", "image/jpeg", "RGB"),
    ("P", "PNG", "image/jpeg", "RGB"),
    ("RGBA", "PNG", "image/png", "RGBA"),
    ("P", "GIF", "image/gif", "P"),
])
def test_home_assistant_thumbnail_processing(tmp_path, mode, input_format, content_type, output_mode):
    original = tmp_path / "original"
    target = tmp_path / "thumbnail"
    Image.new(mode, (640, 480)).save(original, format=input_format)

    _generate_thumbnail_if_file_does_not_exist(target, original, content_type, target, (256, 256))

    with Image.open(target) as result:
        result.load()
        assert result.size == (256, 192)
        assert result.mode == output_mode
        assert result.format == content_type.split("/")[-1].upper()


def test_home_assistant_thumbnail_honours_exif_orientation(tmp_path):
    original = tmp_path / "original"
    target = tmp_path / "thumbnail"
    image = Image.new("RGB", (640, 480), "red")
    exif = image.getexif()
    exif[274] = 6
    image.save(original, format="JPEG", exif=exif)

    _generate_thumbnail_if_file_does_not_exist(target, original, "image/jpeg", target, (256, 256))

    with Image.open(target) as result:
        result.load()
        assert result.size == (192, 256)
        assert result.getexif().get(274) is None


def test_home_assistant_bounding_box_and_font_rendering():
    image = Image.new("RGB", (200, 100), "black")
    draw_box(ImageDraw.Draw(image), (0.3, 0.2, 0.8, 0.9), 200, 100, text="OVO test")
    assert image.getpixel((40, 30)) == (255, 255, 0)
    assert image.getpixel((0, 0)) == (0, 0, 0)
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    encoded.seek(0)
    with Image.open(encoded) as result:
        result.load()
        assert result.size == image.size
        assert result.getpixel((40, 30)) == (255, 255, 0)
