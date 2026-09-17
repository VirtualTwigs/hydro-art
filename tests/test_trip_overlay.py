"""Tests for the trip overlay module (GPX/KML path on base art).

Offline — no GDAL, no network. Pure XML parsing + SVG manipulation.
"""

from __future__ import annotations

import pytest

SAMPLE_GPX = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk>
    <trkseg>
      <trkpt lat="45.5" lon="-122.6"><ele>10</ele></trkpt>
      <trkpt lat="45.6" lon="-122.7"><ele>15</ele></trkpt>
      <trkpt lat="45.7" lon="-122.8"><ele>20</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""

SAMPLE_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <LineString>
        <coordinates>-122.6,45.5,10 -122.7,45.6,15 -122.8,45.7,20</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""

SAMPLE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500"><path d="M10 10 L490 490"/></svg>'


class TestParseGpx:
    def test_extracts_coordinates(self):
        from src.trip_overlay import parse_gpx

        coords = parse_gpx(SAMPLE_GPX)
        assert len(coords) == 3
        assert coords[0] == pytest.approx((45.5, -122.6), abs=0.01)
        assert coords[2] == pytest.approx((45.7, -122.8), abs=0.01)

    def test_invalid_xml_rejected(self):
        from src.trip_overlay import TripOverlayError, parse_gpx

        with pytest.raises(TripOverlayError):
            parse_gpx("not xml at all {{{{")


class TestParseKml:
    def test_extracts_coordinates(self):
        from src.trip_overlay import parse_kml

        coords = parse_kml(SAMPLE_KML)
        assert len(coords) == 3
        # KML is lon,lat,ele — we return (lat, lon)
        assert coords[0] == pytest.approx((45.5, -122.6), abs=0.01)

    def test_invalid_xml_rejected(self):
        from src.trip_overlay import TripOverlayError, parse_kml

        with pytest.raises(TripOverlayError):
            parse_kml("not xml {{{{")


class TestOverlayPathOnSvg:
    def test_adds_polyline_to_svg(self):
        from src.trip_overlay import overlay_path_on_svg

        coords = [(45.5, -122.6), (45.6, -122.7), (45.7, -122.8)]
        result = overlay_path_on_svg(SAMPLE_SVG, coords)
        assert "<polyline" in result or "<path" in result
        assert "</svg>" in result

    def test_preserves_original_content(self):
        from src.trip_overlay import overlay_path_on_svg

        coords = [(45.5, -122.6), (45.6, -122.7)]
        result = overlay_path_on_svg(SAMPLE_SVG, coords)
        assert 'M10 10 L490 490' in result


class TestSurcharge:
    def test_trip_surcharge_50_percent(self):
        from src.trip_overlay import trip_surcharge

        assert trip_surcharge(10000) == 15000  # $100 → $150

    def test_trip_order_requires_file(self):
        from src.trip_overlay import TripOverlayError, validate_trip_order

        with pytest.raises(TripOverlayError, match="[Ff]ile"):
            validate_trip_order(is_trip=True, file_content=None)
