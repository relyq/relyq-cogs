import sqlite3
import json
from datetime import datetime, timezone

with sqlite3.connect("scores.db") as con:
    cur = con.cursor()

    cur.execute(
        """CREATE TABLE guild (
        id INTEGER NOT NULL,
        enabled BOOLEAN NOT NULL,
        sync BOOLEAN NOT NULL,
        cooldown INTEGER NOT NULL,
        grace INTEGER NOT NULL,
        range INTEGER NOT NULL,
        log_channel INTEGER,
        added DATETIME NOT NULL,
        PRIMARY KEY (id)
        )"""
    )

    cur.execute(
        """CREATE TABLE channel (
        id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        grace_count INTEGER NOT NULL,
        pinned BOOLEAN NOT NULL,
        tracked BOOLEAN NOT NULL,
        updated DATETIME NOT NULL,
        added DATETIME NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(guild_id) REFERENCES guild (id) ON DELETE CASCADE
        )"""
    )

    cur.execute(
        """CREATE TABLE category (
        id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        volume VARCHAR(8) NOT NULL,
        volume_pos INTEGER NOT NULL,
        added DATETIME NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT vol_pos UNIQUE (volume, volume_pos),
        FOREIGN KEY(guild_id) REFERENCES guild (id) ON DELETE CASCADE
        )"""
    )

    with open("./settings.json") as f:
        settings = json.load(f)
        settings = settings["1797464170"]["GUILD"]

        guilds = []
        [guilds.append(g) for g in settings]

        for g in guilds:
            print(g)
            log_channel = settings[g]["log_channel"]
            enabled = settings[g]["enabled"]
            sync = settings[g]["sync"]
            cooldown = settings[g]["cooldown"]
            grace = settings[g]["grace"]
            range = settings[g]["range"]
            added = datetime.now(timezone.utc)

            print(f"log_channel: {log_channel}")
            print(f"enabled: {enabled}")
            print(f"sync: {sync}")
            print(f"cooldown: {cooldown}")
            print(f"grace: {grace}")
            print(f"range: {range}")
            print(f"added: {datetime.now(timezone.utc)}")
            print()

            cur.execute(
                "INSERT INTO guild (id, enabled, sync, cooldown, grace, range, log_channel, added) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    int(g),
                    bool(enabled),
                    bool(sync),
                    int(cooldown),
                    int(grace),
                    int(range),
                    int(log_channel),
                    added,
                ],
            )

            channels = []
            [channels.append(c) for c in settings[g]["scoreboard"]]
            for c in channels:
                print(c)
                score = settings[g]["scoreboard"][c]["score"]
                grace_count = settings[g]["scoreboard"][c]["grace_count"]
                pinned = settings[g]["scoreboard"][c]["pinned"]
                tracked = settings[g]["scoreboard"][c]["tracked"]
                updated = settings[g]["scoreboard"][c]["updated"]
                updated = datetime.fromtimestamp(float(updated))
                added = settings[g]["scoreboard"][c]["added"]
                added = datetime.fromtimestamp(float(added))
                print(f"guild_id: {g}")
                print(f"score: {score}")
                print(f"grace_count: {grace_count}")
                print(f"pinned: {pinned}")
                print(f"tracked: {tracked}")
                print(f"updated: {updated}")
                print(f"added: {added} ")
                print()

                cur.execute(
                    "INSERT INTO channel (id, guild_id, score, grace_count, pinned, tracked, updated, added) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        int(c),
                        int(g),
                        int(score),
                        int(grace_count),
                        bool(pinned),
                        bool(tracked),
                        updated,
                        added,
                    ],
                )
            print()
