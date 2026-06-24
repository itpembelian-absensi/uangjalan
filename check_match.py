import importlib
import sys
sys.path.insert(0, 'backend')

# Force reload
if 'app.toll_gate_service' in sys.modules:
    importlib.reload(sys.modules['app.toll_gate_service'])

from app.toll_gate_service import _find_section_for_road, _road_matches_bpjt_section

# Test Kamal-Balaraja
road_name = "Jalan Tol Kamal\u2013Balaraja"
section_name = "Serpong-Balaraja Seksi 1 (Serpong-SS Legok)"
matches = _road_matches_bpjt_section(road_name, section_name, [])
print(f"Road: {road_name}")
print(f"Section: {section_name}")
print(f"Matches: {matches}")

# Test with sections list
sections = [
    {"name": "Serpong-Balaraja Seksi 1 (Serpong-SS Legok)", "id": 29, "rates_by_code": {"II": 5000}},
]
result = _find_section_for_road(road_name, sections)
print(f"\n_find_section_for_road result: {result.get('name') if result else 'NOT FOUND'}")
