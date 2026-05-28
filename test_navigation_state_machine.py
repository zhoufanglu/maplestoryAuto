from navigation import NavContext, NavigationStateMachine


def make_ctx(now_ts, hunters, char=(500, 500), layer="L1", ropes=None):
    return NavContext(
        now_ts=now_ts,
        char_pos=char,
        hunters_pos=hunters,
        current_layer=layer,
        layer_points={"L1": {"left_x": 300, "right_x": 800, "drop_x": 650, "rope_x": 560}},
        anchor_points={"safe_left": 320},
        rope_x_candidates=ropes or [],
        dynamic_rope_x=True,
    )


def run_tests():
    sm = NavigationStateMachine(
        steps=[
            {"action": "move", "anchor": "safe_left", "tol": 10},
            {"action": "climb_up", "anchor": "L1.rope", "tol": 20},
        ],
        no_hunter_timeout_sec=0.2,
        command_cooldown_sec=0.1,
        move_tolerance_px=24,
    )

    t0 = 100.0

    # Combat should suppress patrol commands.
    sm.sync_clock(t0)
    assert sm.next_command(make_ctx(t0, hunters=[(100, 100)])) is None

    # Before timeout, still waiting.
    sm.sync_clock(t0 + 0.1)
    assert sm.next_command(make_ctx(t0 + 0.1, hunters=[])) is None

    # After timeout, move step should emit anchor-resolved x.
    sm.sync_clock(t0 + 0.25)
    cmd = sm.next_command(make_ctx(t0 + 0.25, hunters=[]))
    assert cmd and cmd["action"] == "move" and cmd["x"] == 320

    # Already near target, move step advances then climb_up uses nearest dynamic rope.
    sm.sync_clock(t0 + 0.5)
    cmd = sm.next_command(make_ctx(t0 + 0.5, hunters=[], char=(322, 500), ropes=[540, 575]))
    assert cmd and cmd["action"] == "move"

    sm.sync_clock(t0 + 0.7)
    cmd = sm.next_command(make_ctx(t0 + 0.7, hunters=[], char=(322, 500), ropes=[540, 575]))
    assert cmd and cmd["action"] == "climb_up" and cmd["x"] == 560

    print("test_navigation_state_machine.py passed")


if __name__ == "__main__":
    run_tests()


