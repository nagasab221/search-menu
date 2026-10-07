#!/usr/bin/env bash
# installs Search Menu in place of Cinnamon's menu
#   ./install.sh            install or update
#   ./install.sh --remove   put the normal menu back
set -euo pipefail

UUID="search-menu@fabri"
REPO="nagasab221/search-menu"
STOCK="/usr/share/cinnamon/applets/menu@cinnamon.org"
DEST="$HOME/.local/share/cinnamon/applets/$UUID"
SPICES="$HOME/.config/cinnamon/spices"

# everything runs from main at the very end, so a half-downloaded script does nothing
main() {
    if [[ $EUID -eq 0 ]]; then
        echo "run this as your normal user, not with sudo (it installs just for you)" >&2
        exit 1
    fi
    if ! command -v cinnamon >/dev/null || [[ ! -d "$STOCK" ]]; then
        echo "cinnamon isn't installed on this machine, this needs the cinnamon desktop" >&2
        echo "(desktop here: ${XDG_CURRENT_DESKTOP:-none detected})" >&2
        exit 1
    fi

    # when run through curl the repo files aren't here, so grab the repo first
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd)"
    if [[ ! -f "$script_dir/build.py" ]]; then
        TMP="$(mktemp -d)"
        trap 'rm -rf "$TMP"' EXIT
        echo "downloading search-menu..."
        curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar xz -C "$TMP" --strip-components=1
        bash "$TMP/install.sh" "$@" </dev/null
        exit $?
    fi

    find_session

    if [[ "${1:-}" == "--remove" ]]; then
        if swap_panel "$script_dir" remove && [[ -n "$LIVE" ]]; then
            sleep 1  # let cinnamon unload it before the files go
        fi
        rm -rf "$DEST"
        echo "removed, the normal menu is back"
        exit 0
    fi

    # built from the menu that came with this cinnamon, so it always matches the version
    BUILD="$(mktemp -d)"
    trap 'rm -rf "$BUILD"' EXIT
    local version
    version="$(timeout 5 cinnamon --version 2>/dev/null || true)"
    if ! python3 "$script_dir/build.py" "$STOCK" "$BUILD/$UUID" "${version:-Cinnamon}"; then
        echo >&2
        echo "this cinnamon (${version:-unknown version}) changed its menu in a way search-menu doesn't expect yet." >&2
        echo "nothing was changed, your menu is as it was." >&2
        exit 1
    fi
    mkdir -p "$(dirname "$DEST")"
    rm -rf "$DEST"
    cp -r "$BUILD/$UUID" "$DEST"

    local msg
    if swap_panel "$script_dir" install; then
        msg="installed"
    else
        # already on the panel, just reload it
        [[ -n "$LIVE" ]] && gdbus call --session --dest org.Cinnamon --object-path /org/Cinnamon \
            --method org.Cinnamon.ReloadXlet "$UUID" APPLET >/dev/null 2>&1 || true
        msg="updated"
    fi
    if [[ -n "$LIVE" ]]; then
        echo "$msg, open the menu to try it"
    else
        echo "$msg. cinnamon isn't running right now, it'll show up the next time you log in"
    fi
}

# over ssh or from a text console none of the desktop's environment is set. if cinnamon is
# running for this user, talk to that session instead. if it isn't, write the settings
# straight to disk and the menu shows up at the next login
find_session() {
    LIVE=""
    local pid
    pid="$(pgrep -u "$(id -u)" -x cinnamon | head -n1 || true)"
    if [[ -n "$pid" ]]; then
        LIVE=1
        local var val
        for var in DBUS_SESSION_BUS_ADDRESS DISPLAY XDG_CURRENT_DESKTOP; do
            val="$(tr '\0' '\n' < "/proc/$pid/environ" | sed -n "s/^$var=//p" | head -n1)"
            [[ -n "$val" ]] && export "$var=$val"
        done
    elif ! command -v dbus-run-session >/dev/null; then
        echo "cinnamon isn't running for ${USER:-$(id -un)}, log into the cinnamon desktop and run this again" >&2
        exit 1
    fi
}

gs() {
    if [[ -n "$LIVE" ]]; then
        gsettings "$@"
    else
        # the temporary dbus chatters on stderr, keep only gsettings own errors
        dbus-run-session -- bash -c 'gsettings "$@" 2>&3' _ "$@" 3>&2 2>/dev/null
    fi
}

# swaps the menu on the panel ($2 = install or remove), keeping its place and settings.
# fails if there was nothing to swap
swap_panel() {
    local out
    out="$(python3 "$1/panel.py" "$2" "$(gs get org.cinnamon enabled-applets)" \
        "$(gs get org.cinnamon next-applet-id)" "$SPICES")"
    [[ -n "$out" ]] || return 1
    # counter first: cinnamon numbers any id-less entries from it when the list changes
    gs set org.cinnamon next-applet-id "$(sed -n 2p <<<"$out")"
    gs set org.cinnamon enabled-applets "$(sed -n 1p <<<"$out")"
}

main "$@"
