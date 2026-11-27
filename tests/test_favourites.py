"""To do 27: favourite fleets saved as copies, reused, offered only once."""
import json
from src.favourites import save_favourite, favourite_fleets, to_offer, is_favourite


def _fleet(tmp_path, name="Gothic Sector", n=1):
    p = tmp_path / f"f{n}.json"
    p.write_text(json.dumps({"fleet_name": name, "ships": [{"name": f"Lunar {n}"}]}))
    return str(p)


def test_save_reuse_and_number(tmp_path):
    fav = str(tmp_path / "fav")
    a = save_favourite(_fleet(tmp_path), fav)
    assert a.endswith("gothic_sector.json") and json.load(open(a))["favourite"]
    assert save_favourite(_fleet(tmp_path), fav) == a           # same fleet: reused
    b = save_favourite(_fleet(tmp_path, n=2), fav)              # same name, other ships
    assert b.endswith("gothic_sector_1.json")
    assert favourite_fleets(fav) == sorted([a, b])
    assert is_favourite(a, fav)
    offer = to_offer({1: a, 2: _fleet(tmp_path, n=3)}, fav)
    assert list(offer) == [2]                                    # already a favourite
