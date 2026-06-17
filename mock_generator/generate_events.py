# -*- coding: utf-8 -*-
"""Generate CreatorPulse standard video_stats events for Flume spooldir."""

from __future__ import print_function

import argparse
import codecs
import json
import os
import random
import time
from datetime import datetime

try:
    basestring
except NameError:
    basestring = str


DEFAULT_SPOOL_DIR = "/opt/creatorpulse/data/flume_spool/video_stats"
DEFAULT_STATE_FILE = "/opt/creatorpulse/data/generator_state/state.json"
DEFAULT_PLATFORM_FILTER = "BOUND"

VIDEOS = [
    {
        "creator_id": "creator_003",
        "creator_name": "数码效率研究所",
        "content_id": "video_douyin_01_c3",
        "platform": "DOUYIN",
        "title": "AI办公工具测评：三分钟搭好日报流程",
        "content_type": "TUTORIAL",
        "publish_time": "2026-06-16T09:00:00+08:00",
        "tags": ["AI办公", "效率工具", "数码测评"],
        "base_play": 128500,
        "base_like": 12500,
        "base_comment": 1850,
        "base_share": 4200,
        "base_save": 8900,
        "base_followers": 3200,
    },
    {
        "creator_id": "creator_003",
        "creator_name": "数码效率研究所",
        "content_id": "video_bilibili_04_c3",
        "platform": "BILIBILI",
        "title": "平板笔记工作流：从会议到复盘",
        "content_type": "REVIEW",
        "publish_time": "2026-06-15T20:30:00+08:00",
        "tags": ["平板笔记", "职场效率", "教程"],
        "base_play": 86300,
        "base_like": 8200,
        "base_comment": 960,
        "base_share": 2100,
        "base_save": 6700,
        "base_followers": 2100,
    },
    {
        "creator_id": "creator_003",
        "creator_name": "数码效率研究所",
        "content_id": "video_xiaohongshu_07_c3",
        "platform": "XIAOHONGSHU",
        "title": "桌搭效率清单：低预算升级工作台",
        "content_type": "SEEDING",
        "publish_time": "2026-06-14T18:10:00+08:00",
        "tags": ["桌搭效率", "高性价比测评", "职场效率"],
        "base_play": 64200,
        "base_like": 6100,
        "base_comment": 730,
        "base_share": 1600,
        "base_save": 5200,
        "base_followers": 1700,
    },
]


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def ensure_parent(path):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)


def load_state(path):
    if not os.path.exists(path):
        return {}
    with codecs.open(path, "r", "utf-8") as handle:
        return json.load(handle)


def save_state(path, state):
    ensure_parent(path)
    tmp_path = path + ".tmp"
    with codecs.open(tmp_path, "w", "utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp_path, path)


def json_line(value):
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(rendered, bytes):
        rendered = rendered.decode("utf-8")
    return rendered + "\n"


def parse_json_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def iso_from_mysql_datetime(value):
    text = str(value)
    if "T" in text:
        return text
    return text.replace(" ", "T") + "+08:00"


def build_videos_from_bindings(rows):
    videos = []
    for row in rows:
        views = int(row.get("views") or 1000)
        likes = int(row.get("likes") or max(40, views * 0.08))
        comments = int(row.get("comments") or max(6, views * 0.01))
        shares = int(row.get("shares") or max(4, views * 0.008))
        saves = int(row.get("saves") or max(8, views * 0.016))
        followers = int(row.get("new_followers") or max(10, views * 0.012))
        videos.append(
            {
                "creator_id": row["creator_id"],
                "creator_name": row.get("display_name") or row["creator_id"],
                "content_id": row["video_id"],
                "platform": row["platform"],
                "title": row.get("title") or row["video_id"],
                "content_type": row.get("content_type") or "TUTORIAL",
                "publish_time": iso_from_mysql_datetime(row.get("publish_time") or now_iso()),
                "tags": parse_json_list(row.get("topic_tags")),
                "base_play": views,
                "base_like": likes,
                "base_comment": comments,
                "base_share": shares,
                "base_save": saves,
                "base_followers": followers,
            }
        )
    return videos


def load_env_file(path):
    if not path or not os.path.exists(path):
        return
    with codecs.open(path, "r", "utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_bound_video_rows(env_file=None, require_db=False):
    load_env_file(env_file)
    required = ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        if require_db:
            raise RuntimeError("Missing MySQL config: %s" % ", ".join(missing))
        return []

    try:
        import pymysql
    except ImportError as exc:
        if require_db:
            raise RuntimeError("PyMySQL is required when --require-db is used") from exc
        return []

    connection = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  c.creator_id,
                  c.display_name,
                  pa.platform,
                  v.video_id,
                  v.title,
                  v.content_type,
                  v.topic_tags,
                  v.publish_time,
                  COALESCE(vms.views, 1000) AS views,
                  COALESCE(vms.likes, 80) AS likes,
                  COALESCE(vms.comments, 10) AS comments,
                  COALESCE(vms.shares, 8) AS shares,
                  COALESCE(vms.saves, 16) AS saves,
                  COALESCE(vms.new_followers, 20) AS new_followers
                FROM platform_accounts pa
                JOIN creators c ON c.creator_id = pa.creator_id
                JOIN videos v ON v.creator_id = pa.creator_id AND v.platform = pa.platform
                LEFT JOIN video_metric_snapshots vms
                  ON vms.snapshot_id = (
                    SELECT latest.snapshot_id
                    FROM video_metric_snapshots latest
                    WHERE latest.video_id = v.video_id
                    ORDER BY latest.collected_at DESC, latest.snapshot_id DESC
                    LIMIT 1
                  )
                WHERE pa.binding_status = 'BOUND'
                ORDER BY c.creator_id, pa.platform, v.publish_time DESC, v.video_id
                """
            )
            return list(cursor.fetchall())
    finally:
        connection.close()


def load_video_templates(env_file=None, require_db=False):
    bound_rows = load_bound_video_rows(env_file, require_db=require_db)
    if require_db and not bound_rows:
        raise RuntimeError("No bound platform videos were found in MySQL")
    if not bound_rows:
        return VIDEOS
    videos = build_videos_from_bindings(bound_rows)
    random.shuffle(videos)
    return videos


def next_counter(state, key, base_value, minimum_step, maximum_step):
    current = int(state.get(key, base_value))
    step = random.randint(minimum_step, maximum_step)
    state[key] = current + step
    return state[key], step


def make_event(video, state, sequence):
    fetch_time = now_iso()
    prefix = "%s:%s" % (video["creator_id"], video["content_id"])
    play_count, play_growth_5s = next_counter(state, prefix + ":play", video["base_play"], 80, 420)
    like_count, _ = next_counter(state, prefix + ":like", video["base_like"], 8, 38)
    comment_count, _ = next_counter(state, prefix + ":comment", video["base_comment"], 1, 9)
    share_count, _ = next_counter(state, prefix + ":share", video["base_share"], 2, 16)
    save_count, _ = next_counter(state, prefix + ":save", video["base_save"], 4, 28)
    followers, follower_step = next_counter(state, prefix + ":followers", video["base_followers"], 2, 18)
    profile_visits = max(followers * random.randint(4, 8), 1)
    interactions = like_count + comment_count + share_count + save_count
    interaction_rate = round(float(interactions) / float(play_count), 6)
    conversion_rate = round(float(follower_step) / float(play_growth_5s), 6)
    event_id = "evt_%s_%s_%d" % (video["content_id"], int(time.time()), sequence)

    return {
        "topic": "video_stats_topic",
        "event_id": event_id,
        "event_type": "video_stats",
        "platform": video["platform"],
        "fetch_time": fetch_time,
        "creator_id": video["creator_id"],
        "creator_name": video["creator_name"],
        "content_id": video["content_id"],
        "title": video["title"],
        "content_type": video["content_type"],
        "publish_time": video["publish_time"],
        "publish_hour": int(video["publish_time"][11:13]),
        "tags": video["tags"],
        "stats": {
            "play_count": play_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "share_count": share_count,
            "save_count": save_count,
            "interaction_rate": interaction_rate,
            "completion_rate": round(random.uniform(0.52, 0.78), 6),
            "average_watch_seconds": random.randint(58, 220),
        },
        "growth": {
            "play_growth_5s": play_growth_5s,
            "play_growth_1h": play_growth_5s * random.randint(34, 58),
            "is_accelerating": play_growth_5s >= 220,
            "velocity_score": round(min(100.0, interaction_rate * 420), 2),
            "new_followers": follower_step,
            "profile_visits": profile_visits,
        },
        "traffic_source": {
            "recommend": {
                "views": int(play_count * 0.52),
                "view_ratio": 0.52,
                "new_followers": int(follower_step * 0.46),
                "conversion_rate": conversion_rate,
            },
            "search": {
                "views": int(play_count * 0.2),
                "view_ratio": 0.2,
                "new_followers": int(follower_step * 0.26),
                "conversion_rate": conversion_rate,
            },
            "follow": {
                "views": int(play_count * 0.16),
                "view_ratio": 0.16,
                "new_followers": int(follower_step * 0.2),
                "conversion_rate": conversion_rate,
            },
        },
    }


def write_batch(spool_dir, state_file, batch_size, videos=None):
    if not os.path.exists(spool_dir):
        os.makedirs(spool_dir)
    state = load_state(state_file)
    video_templates = videos or VIDEOS
    events = []
    for index in range(batch_size):
        video = video_templates[index % len(video_templates)]
        events.append(make_event(video, state, index + 1))

    batch_name = "video_stats_%s_%d" % (datetime.now().strftime("%Y%m%d_%H%M%S"), os.getpid())
    tmp_path = os.path.join(spool_dir, batch_name + ".tmp")
    final_path = os.path.join(spool_dir, batch_name + ".json")
    with codecs.open(tmp_path, "w", "utf-8") as handle:
        for event in events:
            handle.write(json_line(event))
    os.rename(tmp_path, final_path)
    save_state(state_file, state)
    return final_path, len(events)


def main():
    parser = argparse.ArgumentParser(description="Generate CreatorPulse video_stats JSON Lines files for Flume")
    parser.add_argument("--spool-dir", default=DEFAULT_SPOOL_DIR)
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--require-db", action="store_true")
    args = parser.parse_args()

    while True:
        videos = load_video_templates(args.env_file, require_db=args.require_db)
        path, count = write_batch(args.spool_dir, args.state_file, args.batch_size, videos)
        print("generated %s events -> %s" % (count, path))
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
