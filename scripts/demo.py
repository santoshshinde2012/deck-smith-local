"""Run one deck end to end as each test user and print what happened."""

from __future__ import annotations

from decksmith.bootstrap import build_container
from decksmith.domain.principal import Principal

REQUEST = "Build the Q3 2026 customer retention review for the exec team"


def main() -> None:
    container = build_container()
    try:
        for user in ("bob", "alice", "carol"):
            principal = Principal(user_id=user, token=f"{user}-token")
            view = container.service.start(REQUEST, principal)
            print(f"{user}: outline {[s['slide_id'] for s in (view.outline or {}).get('slides', [])]}")
            view = container.service.decide(view.run_id, "approve", principal)
            if view.artifact:
                deck = view.artifact
                print(f"  deck {deck['path']} ({deck['slide_count']} slides, {len(view.facts)} facts)")
            else:
                print(f"  {view.status}: {view.error}")
    finally:
        container.close()


if __name__ == "__main__":
    main()
