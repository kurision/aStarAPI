import math
import json
import psycopg2.pool


pool = psycopg2.pool.SimpleConnectionPool(
    host="localhost",
    port="5432",
    database="routing_db",
    user="postgres",
    password="password",
    minconn=1,
    maxconn=10,
)


class LatLan:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude


def heuristic_haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # metres
    phi1 = (lat1 * math.pi) / 180
    phi2 = (lat2 * math.pi) / 180
    delta_phi = ((lat2 - lat1) * math.pi) / 180
    delta_lambda = ((lon2 - lon1) * math.pi) / 180
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c  # in metres
    return d

def a_star_db(start: LatLan, end: LatLan):
    client = pool.getconn()
    query_str = f"""
        SELECT ST_AsGeoJSON(ST_Union((the_geom))) FROM ways WHERE gid in
        (SELECT edge FROM pgr_astar(
            'SELECT gid as id,
            source,
            target,
            length AS cost,
            x1, y1, x2, y2
            FROM ways',
            (SELECT id FROM ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_Point({start.longitude}, {start.latitude}), 4326) LIMIT 1), 
            (SELECT id FROM ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_Point({end.longitude}, {end.latitude}), 4326) LIMIT 1),
            directed := false) foo LIMIT 1);
        """
    cursor = client.cursor()
    cursor.execute(query_str)
    res = cursor.fetchone()
    result = res[0]
    client.commit()
    pool.putconn(client)
    return json.loads(result)


async def get_nodes(coordinates):
    nodes = []
    for coordinate in coordinates:
        query = (
            "SELECT id, ST_X(the_geom) AS lon, ST_Y(the_geom) AS lat FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326) LIMIT 1"
        )
        values = [coordinate[0], coordinate[1]]
        async with pool.acquire() as client:
            async with client.cursor() as cursor:
                await cursor.execute(query, values)
                result = await cursor.fetchone()
                nodes.append(result)
    return nodes


def get_coordinates(nodes):
    coordinates = []
    for node in nodes:
        coordinates.append([node[1], node[2]])
    return coordinates


async def get_neighbors(node_id):
    query = """
        SELECT ways.id, ways.name, ways.source, ways.target, ways.the_geom
        FROM ways_vertices_pgr
        JOIN ways ON ways_vertices_pgr.edge = ways.id
        WHERE ways_vertices_pgr.id = %s
    """
    async with pool.acquire() as client:
        async with client.cursor() as cursor:
            await cursor.execute(query, [node_id])
            result = await cursor.fetchall()
            return [
                {"id": res[0], "name": res[1], "source": res[2], "target": res[3], "geometry": json.loads(res[4])}
for res in result
]

async def get_route(start_coordinates, end_coordinates):
    nodes_start = await get_nodes(start_coordinates)
    nodes_end = await get_nodes(end_coordinates)
    start_latlan = LatLan(nodes_start[0][2], nodes_start[0][1])
    end_latlan = LatLan(nodes_end[0][2], nodes_end[0][1])
    path = a_star_db(start_latlan, end_latlan)
    coordinates = get_coordinates(path["coordinates"])
    return coordinates

