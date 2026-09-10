"""Fetch missing villages per subdistrict for large districts where total >500 cap.

Uses lgd_villages where dtname and sdtname to bypass 500 cap.
"""
import json, urllib.parse, urllib.request, time, datetime as dt, logging
from sqlalchemy import select
from app.db.models import Location
from app.db.session import session_scope

API="https://bharatlas.com/api/v1"
UA={"User-Agent":"GramBizAI/1.0 (TN per-sdt fetch)"}
LARGE_DISTRICTS=["Cuddalore","Villupuram","Chengalpattu","Dharmapuri","Salem","Tiruvannamalai","Thanjavur","Thiruvallur","Madurai","Tiruchirappalli","Tirunelveli","Vellore","Thiruvarur","Kallakurichi","Kanchipuram","Coimbatore","Dindigul"]

def fetch_subdistricts(district):
    url=f"{API}/layers/lgd_subdistricts/query?where=dtname={urllib.parse.quote(district)}&limit=100&select=sdtname"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        d=json.load(r)
    return [x.get("sdtname") for x in d.get("data",{}).get("rows",[]) if x.get("sdtname")]

def fetch_villages_sdt(district, sdtname):
    # Use sdtname alone (more reliable than dtname+sdtname AND which returns 0 for some combos)
    # sdtname is unique enough per district, and villages with that sdtname will be filtered by district check later
    rows=[]; offset=0
    while True:
        # Use sdtname filter alone – dtname filter with AND fails for some combos (returns 0)
        q={"where":f"sdtname={sdtname}","limit":"500","select":"vilname11,vilcode11,dtname,stname,gp_name,sdtname,_lat,_lng"}
        if offset: q["offset"]=str(offset)
        params=urllib.parse.urlencode(q)
        url=f"{API}/layers/lgd_villages/query?{params}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            d=json.load(r)
        batch=d.get("data",{}).get("rows",[])
        if not batch: break
        # Filter by district dtname to ensure we only add villages for this district (since sdtname may exist in other districts)
        filtered=[b for b in batch if (b.get("dtname") or "").lower()==district.lower()]
        rows.extend(filtered)
        # If batch <500, no more pages for this sdtname
        if len(batch)<500: break
        offset+=len(batch)
        time.sleep(0.3)
        # If we filtered many out, continue fetching next offset for this sdtname
        if len(filtered)==0 and len(batch)==500:
            # Still need to fetch next page for this sdtname
            continue
    return rows

def ingest():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log=logging.getLogger("per_sdt")
    with session_scope() as db:
        existing={( (r.state or "").lower(), (r.district or "").lower(), (r.village or "").lower() ): True for r in db.execute(select(Location)).scalars()}
        total_created=0
        for district in LARGE_DISTRICTS:
            try:
                sdt_list=fetch_subdistricts(district)
            except Exception as ex:
                print(f"subdistricts {district} fail {ex}"); continue
            print(f"District {district} {len(sdt_list)} subdistricts {sdt_list[:3]}")
            for sdt in sdt_list:
                try:
                    rows=fetch_villages_sdt(district, sdt)
                except Exception as ex:
                    print(f"  {district}/{sdt} fail {ex}"); continue
                if not rows: continue
                added=0
                for r in rows:
                    vname=r.get("vilname11","").strip()
                    if not vname or vname in (" ",): continue
                    lat=r.get("_lat"); lon=r.get("_lng")
                    if lat is None or lon is None: continue
                    key=("tamil nadu", district.lower(), vname.lower())
                    if key in existing: continue
                    loc=Location(
                        state="Tamil Nadu", district=district, block=sdt, village=vname,
                        latitude=float(lat), longitude=float(lon),
                        geo_precision="village",
                        source_name="Local Government Directory via Bharat Atlas (lgd_villages)",
                        source_url="https://bharatlas.com/layers/lgd_villages",
                        dataset_name="LGD Villages 2024 (Tamil Nadu) per-sdt",
                        source_type="government",
                        geographic_level="village", confidence="high",
                        is_estimate=False, is_demo=False,
                        methodology="Official LGD 2024 village centroid per sdtname split to bypass 500 cap; high confidence.",
                        metadata_json={"vilcode11": r.get("vilcode11"), "sdtname": sdt, "dtname": district},
                        retrieved_at=dt.datetime.now(dt.timezone.utc),
                    )
                    db.add(loc); existing[key]=True; added+=1; total_created+=1
                if added:
                    print(f"  {district}/{sdt}: {len(rows)} LGD villages, {added} new")
                    db.commit()
                time.sleep(0.3)
        print(f"Done per-sdt missing villages added {total_created}")
        db.commit()

if __name__=="__main__":
    ingest()
