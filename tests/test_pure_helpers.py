"""
Unit tests for tapium.py's pure/near-pure parsing logic:
_bounds_center, _parse_ui, _find_element. None of these need a real
device — _parse_ui/_find_element only need something with a
.dump_hierarchy() method, which tests/conftest.py's FakeDevice provides.
"""

from conftest import FakeDevice
import tapium


# ── _bounds_center ────────────────────────────────────────────────────────────

def test_bounds_center_parses_valid_bounds():
    assert tapium._bounds_center("[100,200][300,400]") == (200, 300)


def test_bounds_center_handles_single_digit_and_negative_free_input():
    assert tapium._bounds_center("[0,0][1080,2400]") == (540, 1200)


def test_bounds_center_returns_none_for_garbage():
    assert tapium._bounds_center("not-bounds") is None


def test_bounds_center_returns_none_for_empty_string():
    assert tapium._bounds_center("") is None


def test_bounds_center_returns_none_for_wrong_number_count():
    # Only 3 numbers instead of the expected 4.
    assert tapium._bounds_center("[100,200][300]") is None


# ── _parse_ui ─────────────────────────────────────────────────────────────────

SAMPLE_XML = """<hierarchy>
  <node text="Sign in" content-desc="" class="android.widget.Button"
        clickable="true" scrollable="false" bounds="[100,200][300,260]" />
  <node text="" content-desc="" class="android.widget.LinearLayout"
        clickable="false" scrollable="false" bounds="[0,0][1080,2400]" />
  <node text="Email" content-desc="" class="android.widget.EditText"
        clickable="true" scrollable="false" bounds="[50,300][1000,360]" />
  <node text="" content-desc="Profile picture" class="android.widget.ImageView"
        clickable="true" scrollable="false" bounds="[900,10][1000,110]" />
  <node text="Feed" content-desc="" class="android.widget.ListView"
        clickable="false" scrollable="true" bounds="[0,400][1080,2000]" />
</hierarchy>"""


def test_parse_ui_skips_elements_with_no_text_or_description():
    d = FakeDevice(xml=SAMPLE_XML)
    elements = tapium._parse_ui(d)
    # The bare LinearLayout has neither text nor content-desc and must be dropped.
    labels = [e["text"] for e in elements]
    assert "" not in labels
    assert len(elements) == 4


def test_parse_ui_falls_back_to_content_desc_when_text_is_empty():
    d = FakeDevice(xml=SAMPLE_XML)
    elements = tapium._parse_ui(d)
    image = next(e for e in elements if e["text"] == "Profile picture")
    assert image["type"] == "ImageView"
    assert image["clickable"] is True


def test_parse_ui_extracts_class_bounds_and_flags_correctly():
    d = FakeDevice(xml=SAMPLE_XML)
    elements = tapium._parse_ui(d)
    button = next(e for e in elements if e["text"] == "Sign in")
    assert button["type"] == "Button"
    assert button["bounds"] == "[100,200][300,260]"
    assert button["clickable"] is True
    assert button["scrollable"] is False

    feed = next(e for e in elements if e["text"] == "Feed")
    assert feed["scrollable"] is True
    assert feed["clickable"] is False


# ── _find_element ─────────────────────────────────────────────────────────────

DUPLICATE_LABEL_XML = """<hierarchy>
  <node text="Save" content-desc="" class="android.widget.TextView"
        clickable="false" enabled="true" bounds="[0,0][100,50]" />
  <node text="Save" content-desc="" class="android.widget.Button"
        clickable="true" enabled="true" bounds="[200,200][400,260]" />
</hierarchy>"""


def test_find_element_prefers_clickable_among_duplicate_labels():
    d = FakeDevice(xml=DUPLICATE_LABEL_XML)
    node = tapium._find_element(d, "Save")
    assert node.attrib.get("clickable") == "true"
    assert node.attrib.get("bounds") == "[200,200][400,260]"


ENABLED_ONLY_XML = """<hierarchy>
  <node text="Retry" content-desc="" class="android.widget.TextView"
        clickable="false" enabled="false" bounds="[0,0][100,50]" />
  <node text="Retry" content-desc="" class="android.widget.TextView"
        clickable="false" enabled="true" bounds="[200,200][400,260]" />
</hierarchy>"""


def test_find_element_falls_back_to_enabled_when_none_clickable():
    d = FakeDevice(xml=ENABLED_ONLY_XML)
    node = tapium._find_element(d, "Retry")
    assert node.attrib.get("enabled") == "true"
    assert node.attrib.get("bounds") == "[200,200][400,260]"


def test_find_element_matches_by_content_desc_too():
    xml = """<hierarchy>
      <node text="" content-desc="Menu" class="android.widget.ImageButton"
            clickable="true" bounds="[10,10][60,60]" />
    </hierarchy>"""
    d = FakeDevice(xml=xml)
    node = tapium._find_element(d, "Menu")
    assert node is not None
    assert node.attrib.get("bounds") == "[10,10][60,60]"


def test_find_element_returns_none_when_no_match():
    d = FakeDevice(xml=SAMPLE_XML)
    assert tapium._find_element(d, "Does Not Exist") is None
