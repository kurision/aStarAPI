from fastapi import Body, FastAPI

from algorithm import LatLan, a_star_db

app = FastAPI()

@app.post("/")

async def root(payload:dict=Body(...)):
    print(payload)
    start_coord = payload['start_coord']
    end_coord = payload['end_coord']
    start_lan = LatLan(start_coord[0], start_coord[1])
    end_lan = LatLan(end_coord[0], end_coord[1])
    coordinates = a_star_db(start_lan,end_lan)
    return coordinates
    return {"message": "Hello World"}