import asyncio
import aiohttp
import time
FEED_URL = "https://www.clubhouseapi.com/api/get_feed_v3"
JOIN_ROOM_URL = "https://www.clubhouseapi.com/api/join_channel"
LEAVE_ROOM_URL = "https://www.clubhouseapi.com/api/leave_channel"
ACTIVE_PING_URL = "https://www.clubhouseapi.com/api/active_ping"
ACCEPT_SPEAKER_INVITE_URL = "https://www.clubhouseapi.com/api/become_speaker"
INVITE_SPEAKER_URL = "https://www.clubhouseapi.com/api/invite_speaker"
USER_PROFILE_URL = "https://www.clubhouseapi.com/api/get_profile"
GET_CHANNEL_URL = "https://www.clubhouseapi.com/api/get_channel"
FOLLOW_USER_URL = "https://www.clubhouseapi.com/api/follow"
MAKE_MODERATOR_URL = "https://www.clubhouseapi.com/api/make_moderator"
MOVE_TO_AUDIENCE_URL = "https://www.clubhouseapi.com/api/uninvite_speaker"
INVITE_COOLDOWN = 120
MODERATOR_USER_IDS = { 526780789, 1037728567, 1960322941, 1598074929, 781717943 }
def get_headers(token: str, user_id: int) -> dict:
    return {
        'CH-UserID': str(user_id), 
        'Authorization': 'Token ' + token,
        'Content-Type': 'application/json; charset=utf-8',
        'CH-AppVersion': '1.0.9',
        'CH-AppBuild': '305',
        'Accept': 'application/json'
    }

async def post(session, url, headers, data):
    try:
        async with session.post(url, headers=headers, json=data) as resp:
            status = resp.status
            try:
                json_resp = await resp.json(content_type=None)
            except aiohttp.ContentTypeError:
                json_resp = {}
            return status, json_resp
    except Exception as e:
        print(f"❌ Error calling {url}: {e}")
        return None, None
async def move_to_audience(session, token, bot_id, channel_id, user_id, name=None):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id, "user_id": user_id}
    status, _ = await post(session, MOVE_TO_AUDIENCE_URL, headers, data)
    if status == 200:
        print(f"🔇 Moved {name or user_id} to audience in {channel_id}")
    else:
        print(f"⚠ Failed to move {name or user_id} to audience, status: {status}")
async def invite_speaker(session, token, bot_id, channel_id, user_id, name=None):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id, "user_id": user_id}
    async with session.post(INVITE_SPEAKER_URL, headers=headers, json=data) as resp:
        if resp.status == 200:
            print(f"✅ Invited {name or user_id} to speak in {channel_id}")
        else:
            print(f"⚠ Failed to invite {name or user_id}, status: {resp.status}")
async def make_moderator(session, token, bot_id, channel_id, user_id):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id, "user_id": user_id}
    status, _ = await post(session, MAKE_MODERATOR_URL, headers, data)
    if status == 200:
        print(f"⭐ Made user {user_id} a moderator in {channel_id}")
    else:
        print(f"⚠ Failed to make user {user_id} moderator, status: {status}")
async def become_speaker(session, token, bot_id, channel_id):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id}
    status, _ = await post(session, ACCEPT_SPEAKER_INVITE_URL, headers, data)
    if status == 200:
        print(f"🙋 Became a speaker in {channel_id}")
    elif status == 429:
        print("⚠ Rate limited while trying to become speaker. Retrying in 30s.")
        await asyncio.sleep(30)
        await become_speaker(session, token, bot_id, channel_id)
    else:
        print(f"❌ Failed to become speaker in {channel_id}, status: {status}")
async def invite_all_users(session, token, bot_id, channel_id, invited_users):
    headers = get_headers(token, bot_id)
    status, data = await post(session, GET_CHANNEL_URL, headers, {"channel": channel_id})
    if status == 200 and data:
        current_time = time.time()
        tasks = []
        for user in data.get("users", []):
            user_id = user.get("user_id")
            name = user.get("name")
            is_speaker = user.get("is_speaker", False)
            is_moderator = user.get("is_moderator", False)
            if is_moderator and user_id not in MODERATOR_USER_IDS:
                asyncio.create_task(move_to_audience(session, token, bot_id, channel_id, user_id, name))
                continue
            if user_id in MODERATOR_USER_IDS and is_speaker and not is_moderator:
                await make_moderator(session, token, bot_id, channel_id, user_id)
            if user_id == bot_id and not is_speaker:
                asyncio.create_task(become_speaker(session, token, bot_id, channel_id))
            last_invite_time = invited_users.get(user_id, 0)
            if user_id != bot_id and not is_speaker and not is_moderator and (current_time - last_invite_time) > INVITE_COOLDOWN:
                invited_users[user_id] = current_time
                tasks.append(invite_speaker(session, token, bot_id, channel_id, user_id, name))
        if tasks:
            await asyncio.gather(*tasks)

async def accept_speaker_invite(session, token, bot_id, channel_id, retries=3):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id}
    for _ in range(retries):
        status, _ = await post(session, ACCEPT_SPEAKER_INVITE_URL, headers, data)
        if status == 200:
            print(f"🙋 Accepted speaker invite in room: {channel_id}")
            return
        elif status in {400, 404}:
            return
        await asyncio.sleep(4)
async def follow_user(session, token, bot_id, user_id, name=None):
    headers = get_headers(token, bot_id)
    data = {"user_id": user_id}
    try:
        async with session.post(FOLLOW_USER_URL, headers=headers, json=data) as resp:
            if resp.status == 200:
                print(f"👤 Followed {name or user_id}")
            elif resp.status == 429:
                print("⚠ Rate limited on follow. Sleeping 60s.")
                await asyncio.sleep(60)
                return await follow_user(session, token, bot_id, user_id, name)
            else:
                print(f"❌ Failed to follow {name or user_id}, status: {resp.status}")
    except Exception as e:
        print(f"❌ Error while following {name or user_id}: {e}")
async def auto_follow_users(session, token, bot_id, channel_id, followed_users):
    headers = get_headers(token, bot_id)
    while True:
        status, data = await post(session, GET_CHANNEL_URL, headers, {"channel": channel_id})
        if status == 200 and data:
            for user in data.get("users", []):
                user_id = user.get("user_id")
                name = user.get("name")
                if user_id != bot_id and user_id not in followed_users:
                    followed_users.add(user_id)
                    asyncio.create_task(follow_user(session, token, bot_id, user_id, name))
        await asyncio.sleep(10)

async def active_ping(session, token, bot_id, channel_id):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id}
    while True:
        status, _ = await post(session, ACTIVE_PING_URL, headers, data)
        if status == 200:
            print(f"📱 Sent active ping in room: {channel_id}")
        else:
            print(f"⚠ Failed to send active ping, status: {status}")
        await asyncio.sleep(15)

async def poll_for_speaker_invite(session, token, bot_id, channel_id):
    headers = get_headers(token, bot_id)
    while True:
        status, data = await post(session, GET_CHANNEL_URL, headers, {"channel": channel_id})
        if status == 200 and data:
            for user in data.get("users", []):
                if user.get("user_id") == bot_id:
                    if not user.get("is_speaker", False) and user.get("is_asked_to_speak", False):
                        print("🎤 Received speaker invite — accepting...")
                        await become_speaker(session, token, bot_id, channel_id)
        await asyncio.sleep(5)

async def get_user_id_from_url(session, token, bot_id, username_or_url):
    headers = get_headers(token, bot_id)
    username = username_or_url.strip().rstrip("/").split("/")[-1]
    data = {"username": username}
    try:
        async with session.post(USER_PROFILE_URL, headers=headers, json=data) as resp:
            if resp.status == 200:
                json_resp = await resp.json(content_type=None)
                return json_resp.get("user_profile", {}).get("user_id")
            else:
                print(f"⚠ Failed to get user ID for {username_or_url}, status: {resp.status}")
    except Exception as e:
        print(f"❌ Error fetching user profile: {e}")
    return None

async def find_user_room(session, token, target_user_id, bot_id):
    headers = get_headers(token, bot_id)
    try:
        async with session.post(FEED_URL, headers=headers, json={}) as resp:
            if resp.status == 429:
                print("⚠ Rate limited. Waiting 60s...")
                await asyncio.sleep(60)
                return await find_user_room(session, token, target_user_id, bot_id)
            data = await resp.json(content_type=None)
            for item in data.get("items", []):
                channel = item.get("channel", {})
                for user in channel.get("users", []):
                    if user.get("user_id") == target_user_id:
                        return channel.get("channel")
    except Exception as e:
        print(f"❌ Error getting room feed: {e}")
    return None
async def join_room(session, token, bot_id, channel_id, invited_users):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id}
    status, _ = await post(session, JOIN_ROOM_URL, headers, data)
    if status == 200:
        print(f"✅ Joined room: {channel_id}")
        await accept_speaker_invite(session, token, bot_id, channel_id)
        await invite_all_users(session, token, bot_id, channel_id, invited_users)
    else:
        print(f"⚠ Failed to join room {channel_id}, status: {status}")
async def leave_room(session, token, bot_id, channel_id):
    headers = get_headers(token, bot_id)
    data = {"channel": channel_id}
    await post(session, LEAVE_ROOM_URL, headers, data)
    print(f"👋 Left room: {channel_id}")
async def track_user(token, target_username_or_url, bot_user_id, interval=5):
    current_room = None
    invited_users = {}
    followed_users = set()
    active_ping_task = None
    follow_task = None
    speaker_poll_task = None
    async with aiohttp.ClientSession() as session:
        target_user_id = await get_user_id_from_url(session, token, bot_user_id, target_username_or_url)
        if not target_user_id:
            print(f"❌ Failed to resolve user ID from {target_username_or_url}")
            return
        while True:
            new_room = await find_user_room(session, token, target_user_id, bot_user_id)
            if new_room and new_room != current_room:
                if current_room:
                    for task in [active_ping_task, follow_task, speaker_poll_task]:
                        if task:
                            task.cancel()
                            try: await task
                            except asyncio.CancelledError: pass
                    await leave_room(session, token, bot_user_id, current_room)
                await join_room(session, token, bot_user_id, new_room, invited_users)
                active_ping_task = asyncio.create_task(active_ping(session, token, bot_user_id, new_room))
                follow_task = asyncio.create_task(auto_follow_users(session, token, bot_user_id, new_room, followed_users))
                speaker_poll_task = asyncio.create_task(poll_for_speaker_invite(session, token, bot_user_id, new_room))
                current_room = new_room
            elif not new_room and current_room:
                for task in [active_ping_task, follow_task, speaker_poll_task]:
                    if task:
                        task.cancel()
                        try: await task
                        except asyncio.CancelledError: pass
                await leave_room(session, token, bot_user_id, current_room)
                current_room = None
            if current_room:
                try:
                    await invite_all_users(session, token, bot_user_id, current_room, invited_users)
                except Exception as e:
                    print(f"❌ Error inviting users: {e}")
            await asyncio.sleep(interval)
async def main():
    USERS = [
        {
            "token": "e91c49e4053489a95b0a06f618647e19c8742f86",
            "bot_user_id": 1598074929,
            "target_username": "narcissistbrat"
        },
    ]
    tasks = []
    for user in USERS:
        task = track_user(
            token=user["token"],
            target_username_or_url=user["target_username"],
            bot_user_id=user["bot_user_id"],
            interval=5
        )
        tasks.append(task)
    await asyncio.gather(*tasks)
if __name__ == "__main__":
    asyncio.run(main())