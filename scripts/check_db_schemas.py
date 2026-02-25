import databento as db
import os
os.environ["DATABENTO_API_KEY"] = "db-eLpabYrDC7jnS7XukeVkB4FWRTpsy"
client = db.Historical()

print("XNAS.ITCH schemas:", client.metadata.list_schemas("XNAS.ITCH"))
try:
    print("OPRA.PILLAR schemas:", client.metadata.list_schemas("OPRA.PILLAR"))
except Exception as e:
    print("Error OPRA.PILLAR:", e)
    
try:
    print("OPRA.BBO schemas:", client.metadata.list_schemas("OPRA.BBO"))
except Exception as e:
    print("Error OPRA.BBO:", e)

try:
    print("All OPRA datasets:", [d for d in client.metadata.list_datasets() if "OPRA" in d.upper()])
except:
    pass
