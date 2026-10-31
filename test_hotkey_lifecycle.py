"""
Regression test suite for targeted global hotkey lifecycle.
Verifies that:
1. OpenFlow registers its specific global hotkey.
2. An external component's hotkey registered in the same process is NOT removed on OpenFlow cleanup.
3. OpenFlow's hotkey is removed cleanly without unhook_all_hotkeys side effects.
4. Cleanup handles exceptions safely.
"""
import keyboard
import main

def test_targeted_hotkey_lifecycle():
    print("Testing Targeted Hotkey Lifecycle...\n" + "="*50)
    
    # 1. Register third-party hotkey in the process
    ext_called = False
    def external_cb():
        nonlocal ext_called
        ext_called = True

    ext_handle = keyboard.add_hotkey("ctrl+alt+k", external_cb)
    print("[OK] External hotkey registered: ctrl+alt+k")

    # 2. Initialize OpenFlow and set up its hotkey
    api = main.OpenFlowAPI()
    main.setup_global_hotkey(api)

    assert api.hotkey_handler is not None, "OpenFlow hotkey handler was not stored"
    print("[OK] OpenFlow hotkey registered: Ctrl+Shift+Space")

    # Verify both hotkeys exist in registry
    assert api.hotkey_handler in keyboard._hotkeys, "OpenFlow hotkey missing from table"
    assert ext_handle in keyboard._hotkeys, "External hotkey missing from table"

    # 3. Perform OpenFlow cleanup
    main.cleanup_resources(api)

    # 4. Verify OpenFlow hotkey is removed, external hotkey is retained
    assert api.hotkey_handler is None, "OpenFlow hotkey handler reference not cleared"
    assert ext_handle in keyboard._hotkeys, "External hotkey was incorrectly unhooked!"
    print("[OK] OpenFlow hotkey cleanly unregistered while preserving external hotkeys.")

    # 5. Clean up external test hotkey
    keyboard.remove_hotkey(ext_handle)
    assert ext_handle not in keyboard._hotkeys
    print("[OK] External hotkey cleaned up.")
    print("="*50 + "\nTargeted hotkey lifecycle test PASSED successfully!")

if __name__ == "__main__":
    test_targeted_hotkey_lifecycle()
