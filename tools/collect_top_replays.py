"""Download the newest public episodes for a leaderboard submission manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def first_json_document(output: str):
    output = output.lstrip()
    if not output:
        return []
    value, _ = json.JSONDecoder().raw_decode(output)
    return value


def kaggle_json(*args: str) -> list[dict]:
    completed = subprocess.run(
        ["kaggle", *args, "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # The CLI appends a human-readable replay/logs hint after JSON output.
    # Decode the first document rather than treating that suffix as JSON.
    return first_json_document(completed.stdout)


def newest_public_episode_ids(submission_id: int, limit: int) -> list[int]:
    episodes = kaggle_json("competitions", "episodes", str(submission_id))
    public = [
        episode
        for episode in episodes
        if episode.get("state") == "EpisodeState.COMPLETED"
        and episode.get("type") == "EpisodeType.EPISODE_TYPE_PUBLIC"
    ]
    public.sort(key=lambda episode: str(episode.get("createTime", "")), reverse=True)
    return [int(episode["id"]) for episode in public[:limit]]


def download_replay(episode_id: int, output_dir: Path, attempts: int = 4) -> None:
    for attempt in range(1, attempts + 1):
        completed = subprocess.run(
            [
                "kaggle",
                "competitions",
                "replay",
                str(episode_id),
                "-p",
                str(output_dir),
                "-q",
            ]
        )
        if completed.returncode == 0:
            return
        if attempt == attempts:
            completed.check_returncode()
        time.sleep(2 ** (attempt - 1))


def collect(leaderboard: dict, output_dir: Path, per_agent: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    requests: dict[int, list[dict]] = {}
    entries = []
    all_entries = [
        *(dict(entry, cohort="top20") for entry in leaderboard.get("entries", [])),
        *(dict(entry, cohort="comparator") for entry in leaderboard.get("comparators", [])),
    ]
    for raw in all_entries:
        entry = dict(raw)
        episode_ids = newest_public_episode_ids(int(entry["submission_id"]), per_agent)
        entry["episode_ids"] = episode_ids
        entries.append(entry)
        for episode_id in episode_ids:
            requests.setdefault(episode_id, []).append(
                {
                    "rank": entry["rank"],
                    "name": entry["name"],
                    "replay_name": entry.get("replay_name", entry["name"]),
                    "score": entry["score"],
                    "submission_id": entry["submission_id"],
                    "policy": entry.get("policy", entry["name"]),
                    "cohort": entry["cohort"],
                }
            )

    episodes = []
    for index, episode_id in enumerate(sorted(requests, reverse=True), start=1):
        path = output_dir / f"episode-{episode_id}-replay.json"
        if not path.is_file():
            print(f"download {index}/{len(requests)} episode={episode_id}", flush=True)
            download_replay(episode_id, output_dir)
        episodes.append(
            {
                "episode_id": episode_id,
                "path": str(path),
                "bytes": path.stat().st_size,
                "requested_for": requests[episode_id],
            }
        )

    return {
        "schema": "kaggriculture-top-replay-manifest-v1",
        "competition": leaderboard.get("competition", "kaggriculture"),
        "leaderboard_captured_at": leaderboard.get("captured_at"),
        "per_agent": per_agent,
        "leaderboard_entries": entries,
        "unique_episode_count": len(episodes),
        "episodes": episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leaderboard", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--per-agent", type=int, default=2)
    args = parser.parse_args()
    if args.per_agent < 1:
        parser.error("--per-agent must be positive")
    leaderboard = json.loads(args.leaderboard.read_text(encoding="utf-8"))
    manifest = collect(leaderboard, args.output_dir, args.per_agent)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "agents": len(manifest["leaderboard_entries"]),
                "unique_episodes": manifest["unique_episode_count"],
                "bytes": sum(episode["bytes"] for episode in manifest["episodes"]),
                "manifest": str(args.manifest),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
