from sanic import Sanic, exceptions
from sanic.response import HTTPResponse, text, json as rjson
from sanic.log import logger
from datetime import datetime, time, timedelta
from sanic_scheduler import SanicScheduler, task
import json
from pprint import pprint
import httpx
import aiosqlite
import os
import hashlib
import random
import time
import string

app = Sanic("WUSD")
scheduler = SanicScheduler(app)

@app.listener('before_server_start')
async def init(app, loop):
    app.ctx.db = await aiosqlite.connect(database=os.getcwd() + "/data.db", loop=loop)
    await app.ctx.db.execute("CREATE TABLE IF NOT EXISTS data (key TEXT UNIQUE, val TEXT, uts INTEGER);")

@app.listener('after_server_stop')
async def finish(app, loop):
    await app.ctx.db.close()

# @app.get("/")
# async def h_index(request):
#     return text("Тут ничего нет!", 404)

@app.get("/genshin.json")
async def h_gi_json(_):
    async with _.app.ctx.db.execute("SELECT val, uts FROM data WHERE key = ? LIMIT 1", ( "genshin", )) as cur:
        res = await cur.fetchone()
    if res is None:
        res = await update_resin(_)
    else:
        uts = int(res[1])
        if (time.time() - uts) > 600:
            res = await update_resin(_)
        else:
            res = res[0]
    if res is None:
        raise exceptions.NotFound()
    return HTTPResponse(
        res,
        content_type='application/json'
    )

# @task(timedelta(seconds=5))
async def t_genshin_update(_):
    pass

# @task(timedelta(minutes=10))
async def update_resin(_):
    logger.info("Genshin update task")

    uid = os.getenv('GENSHIN_UID') # 700052312  # int
    ltoken = os.getenv('GENSHIN_LTOKEN') # "m8tRQKWEkVppIxeiAKIKKvQx5jSuNK3XmZYCDtoe"  # str
    ltuid = os.getenv('GENSHIN_LTUID') # "7846854"  # str

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36")

    def generate_ds(salt: str) -> str:
        """Creates a new ds for authentication."""
        t = int(time.time())  # current seconds
        r = "".join(random.choices(string.ascii_letters, k=6))  # 6 random chars
        h = hashlib.md5(f"salt={salt}&t={t}&r={r}".encode()).hexdigest()  # hash and get hex
        return f"{t},{r},{h}"

    OS_DS_SALT="6cqshh5dhw73bzxn20oexa9k516chk7s"

    headers = {
        # required headers
        "x-rpc-app_version": "1.5.0",
        "x-rpc-client_type": "4",
        "x-rpc-language": "en-us",
        # authentications headers
        "ds": generate_ds(OS_DS_SALT),
        # recommended headers
        "user-agent": USER_AGENT
    }

    async with httpx.AsyncClient() as client:
        r = await client.get(
            'https://bbs-api-os.hoyoverse.com/game_record/genshin/api/dailyNote',
            params=dict(server='os_euro', role_id=uid, schedule_type=1),
            headers=headers,
            cookies={'ltuid': ltuid, 'ltoken': ltoken})
        if r.status_code != 200:
            logger.warning("Response status code: " + str(r.status_code))
            return
        try:
            js = json.loads(r.content)
        except:
            logger.warning("Could not decode response")
            return
        if "data" not in js:
            logger.warning("Key data not found in response")
            return
        dt = json.dumps(js['data'])
        async with _.app.ctx.db.execute('INSERT OR REPLACE INTO data (key, val, uts) VALUES (?, ?, ?)', ("genshin", dt, int(time.time()))) as cur:
            await _.app.ctx.db.commit()
    return dt

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=False, single_process=True, motd=False)