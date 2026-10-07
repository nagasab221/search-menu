#!/usr/bin/env python3
"""Builds search-menu@fabri from the menu applet that ships with Cinnamon.

    build.py <stock menu@cinnamon.org dir> <output dir> [cinnamon version]

Every change is an exact text replacement on the stock applet.js. If a Cinnamon
update moved any of them, this stops with an error and writes nothing.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

EDITS = [
    # Session buttons become big labelled tiles in compact mode.
    ("""            styleClass: 'appmenu-system-button',
        });
        this.addIcon(16, iconName, null, true);
""", """            styleClass: 'appmenu-system-button',
        });
        if (applet.compact) {
            this.actor.vertical = true;
            this.actor.add_style_class_name('search-menu-tile');
            this.addIcon(24, iconName, null, true);
            this.addLabel(name, 'search-menu-tile-label');
        } else {
            this.addIcon(16, iconName, null, true);
        }
"""),

    # Own settings file instead of the stock menu's.
    ('new Settings.AppletSettings(this, "menu@cinnamon.org", instance_id);',
     'new Settings.AppletSettings(this, __meta.uuid, instance_id);'),

    ("""        this.settings.bind("popup-height", "popup_height");
""", """        this.settings.bind("popup-height", "popup_height");
        this.settings.bind("compact", "compact", () => {
            this._refreshSystemButtons();
            this._layout();
            this._updateCompact();
        });
"""),

    ("""        this._doRefresh();

        this.set_show_label_in_vertical_panels(false);
    }
""", """        this._doRefresh();
        this._updateCompact();

        this.set_show_label_in_vertical_panels(false);
    }

    // Compact mode: no categories, and the app list only shows up while searching.
    _isCollapsed() {
        return this.compact && !this.searchActive;
    }

    _updateCompact() {
        const collapsed = this._isCollapsed();
        // Search results get exactly the space the home view had, so the menu keeps its size.
        if (this.compact && !collapsed && this._homeBox.visible)
            this._homeHeight = this.main_container.get_preferred_height(-1)[1];
        this.categoriesScrollView.visible = !this.compact;
        this.categoriesApplicationsBox.actor.visible = !collapsed;
        this._homeBox.visible = collapsed;
        this.searchEntry.hint_text = this.compact ? _("Type to search apps") : "";
        this._setMenuSize(this.popup_width, this.popup_height);
    }

    _updateGreeting() {
        const now = GLib.DateTime.new_now_local();
        const hour = now.get_hour();
        let greeting = _("Good evening");
        if (hour >= 5 && hour < 12)
            greeting = _("Good morning");
        else if (hour >= 12 && hour < 18)
            greeting = _("Good afternoon");
        let name = GLib.get_real_name();
        if (!name || name === "Unknown")
            name = GLib.get_user_name();
        this._greetingLabel.set_text(`${greeting}, ${name}`);
        this._dateLabel.set_text(now.format("%A, %-d %B"));
    }
"""),

    # Compact mode never changes the height by resizing; only the width.
    ("""    _onBoxResized(width, height) {
""", """    _onBoxResized(width, height) {
        if (this.compact)
            height = this.popup_height * global.ui_scale;
"""),

    ("""        this.main_container.natural_height = (height * global.ui_scale);
""", """        if (this._isCollapsed())
            this.main_container.natural_height_set = false;
        else
            this.main_container.natural_height = (this.compact && this._homeHeight) || (height * global.ui_scale);
"""),

    ("""            global.stage.set_key_focus(this.searchEntry);
            this._activeContainer = null;
""", """            global.stage.set_key_focus(this.searchEntry);
            this._updateGreeting();
            this._activeContainer = null;
"""),

    # Collapsed: the arrow keys / Tab only move between the session tiles, and
    # Enter only acts on one once it has been selected.
    ("""        if (this._activeContainer === null) {
            this._setKeyFocusToCurrentCategoryButton();
        }
""", """        if (this._isCollapsed()) {
            const current = this._activeContainer === this.systemBox ? this._activeActor : null;
            let target = null;
            switch (symbol) {
                case Clutter.KEY_Right:
                case Clutter.KEY_KP_Right:
                case Clutter.KEY_Down:
                case Clutter.KEY_KP_Down:
                case Clutter.KEY_Tab:
                    target = current ? this.sysBoxIter.next(current) : this.sysBoxIter.first();
                    break;
                case Clutter.KEY_Left:
                case Clutter.KEY_KP_Left:
                case Clutter.KEY_Up:
                case Clutter.KEY_KP_Up:
                case Clutter.KEY_ISO_Left_Tab:
                    target = current ? this.sysBoxIter.prev(current) : this.sysBoxIter.last();
                    break;
                case Clutter.KEY_Return:
                case Clutter.KEY_KP_Enter:
                    if (current) {
                        current._delegate.activate();
                        return Clutter.EVENT_STOP;
                    }
                    break;
            }
            if (!target)
                return Clutter.EVENT_PROPAGATE;
            this._buttonEnterEvent(target._delegate);
            return Clutter.EVENT_STOP;
        }

        if (this._activeContainer === null) {
            this._setKeyFocusToCurrentCategoryButton();
        }
"""),

    # Tiles: add Suspend and Restart, and let every tile take an equal share of the row.
    ("""        this.systemBox.add(button.actor, { y_align: St.Align.MIDDLE, y_fill: false });
""", """        this._addSystemButton(button);
""", 3),

    ("""        //Shutdown button
""", """        if (this.compact) {
            button = new SystemButton(this, "xsi-weather-clear-night",
                                      _("Suspend"),
                                      _("Suspend the computer"));
            // Takes the theme's neutral system-button colours.
            button.actor.add_style_class_name("appmenu-system-button-logout");

            button.activate = () => {
                this.menu.close();
                Util.spawn(["systemctl", "suspend"]);
            };

            this._addSystemButton(button);

            button = new SystemButton(this, "xsi-reboot",
                                      _("Restart"),
                                      _("Restart the computer"));
            button.actor.add_style_class_name("appmenu-system-button-logout");

            button.activate = () => {
                this.menu.close();
                // Asks for confirmation, like Shut Down.
                Util.spawn(["cinnamon-session-quit", "--reboot"]);
            };

            this._addSystemButton(button);
        }

        //Shutdown button
"""),

    ("""    _scrollToButton(button, scrollBox = this.applicationsScrollView) {
""", """    _addSystemButton(button) {
        if (this.compact)
            this.systemBox.add(button.actor, { expand: true, x_fill: true });
        else
            this.systemBox.add(button.actor, { y_align: St.Align.MIDDLE, y_fill: false });
    }

    _scrollToButton(button, scrollBox = this.applicationsScrollView) {
"""),

    ("""            this.categoriesApplicationsBox.actor.remove_style_pseudo_class("top");
""", """            this.right_box.add(this._homeBox, { expand: true });
            this.categoriesApplicationsBox.actor.remove_style_pseudo_class("top");
"""),

    ("""            this.categoriesApplicationsBox.actor.add_style_pseudo_class("top");
""", """            this.right_box.add(this._homeBox, { expand: true });
            this.categoriesApplicationsBox.actor.add_style_pseudo_class("top");
"""),

    ("""        // Position the system box
        if (this.systemPosition == "sidebar")
            global.reparentActor(this.systemBox, this.sidebar);
        else
            global.reparentActor(this.systemBox, this.searchBox);
""", """        // Position the system box
        if (this.compact)
            global.reparentActor(this.systemBox, this._homeBox);
        else if (this.systemPosition == "sidebar")
            global.reparentActor(this.systemBox, this.sidebar);
        else
            global.reparentActor(this.systemBox, this.searchBox);

        this.systemBox.x_align = this.compact ? Clutter.ActorAlign.FILL : Clutter.ActorAlign.CENTER;
        if (this.compact)
            this.systemBox.add_style_class_name('search-menu-tiles');
        else
            this.systemBox.remove_style_class_name('search-menu-tiles');
"""),

    # Compact mode's home view.
    ("""        this.searchSeparator = new PopupMenu.PopupSeparatorMenuItem().actor;
""", """        this.searchSeparator = new PopupMenu.PopupSeparatorMenuItem().actor;

        // Compact mode's view while nothing is typed: a greeting above the session tiles
        // (systemBox is moved in here by _layout).
        this._homeBox = new St.BoxLayout({ style_class: 'search-menu-home', vertical: true });
        let header = new St.BoxLayout({ style_class: 'search-menu-header' });
        let user = AccountsService.UserManager.get_default().get_user(GLib.get_user_name());
        let avatar = new UserWidget.Avatar(user, { iconSize: 52, reactive: false });
        avatar.add_style_class_name('search-menu-avatar');
        const updateAvatar = () => {
            if (user.is_loaded)
                avatar.update();
        };
        const userSignals = [
            user.connect('notify::is-loaded', updateAvatar),
            user.connect('changed', updateAvatar),
        ];
        avatar.connect('destroy', () => userSignals.forEach(id => user.disconnect(id)));
        updateAvatar();
        header.add(avatar, { y_fill: false, y_align: St.Align.MIDDLE });
        let headerText = new St.BoxLayout({ vertical: true });
        this._greetingLabel = new St.Label({ style_class: 'search-menu-greeting' });
        this._dateLabel = new St.Label({ style_class: 'search-menu-date', opacity: 170 });
        headerText.add(this._greetingLabel);
        headerText.add(this._dateLabel);
        header.add(headerText, { expand: true, y_fill: false, y_align: St.Align.MIDDLE });
        this._homeBox.add(header);
        this._updateGreeting();
"""),

    ("""        this.searchActive = searchActive;
        this._clearAllSelections();
""", """        this.searchActive = searchActive;
        this._clearAllSelections();
        this._updateCompact();
"""),
]

COMPACT_SETTING = {
    "type": "switch",
    "default": True,
    "description": "Compact menu",
    "tooltip": "Show a greeting, the session buttons and the search bar. Applications appear when you start typing.",
}


def patch_applet(src):
    for edit in EDITS:
        old, new = edit[0], edit[1]
        count = edit[2] if len(edit) > 2 else 1
        found = src.count(old)
        if found != count:
            first = old.strip().splitlines()[0]
            raise SystemExit(f"applet.js: expected {count} of this line but found {found}:\n    {first}")
        src = src.replace(old, new)
    return src


def patch_schema(schema):
    sections = schema["layout1"]["content"]["sections"]
    if "content-compact" not in sections:
        sections.insert(0, "content-compact")
    schema["layout1"]["content-compact"] = {"type": "section", "title": "Layout", "keys": ["compact"]}
    schema["compact"] = COMPACT_SETTING
    return schema


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    stock, out = sys.argv[1], sys.argv[2]
    version = sys.argv[3] if len(sys.argv) == 4 else None

    # Everything is worked out before anything is written.
    with open(os.path.join(stock, "applet.js")) as f:
        applet = patch_applet(f.read())
    with open(os.path.join(stock, "settings-schema.json")) as f:
        schema = patch_schema(json.load(f))
    with open(os.path.join(HERE, "files", "metadata.json")) as f:
        metadata = json.load(f)
    if version:
        metadata["based-on"] = f"menu@cinnamon.org from {version}"

    os.makedirs(out, exist_ok=True)
    for name in os.listdir(stock):
        if name in ("applet.js", "settings-schema.json", "metadata.json"):
            continue
        path = os.path.join(stock, name)
        if os.path.isdir(path):
            shutil.copytree(path, os.path.join(out, name), dirs_exist_ok=True)
        else:
            shutil.copy(path, out)
    shutil.copy(os.path.join(HERE, "files", "stylesheet.css"), out)
    with open(os.path.join(out, "applet.js"), "w") as f:
        f.write(applet)
    with open(os.path.join(out, "settings-schema.json"), "w") as f:
        json.dump(schema, f, indent=4)
    with open(os.path.join(out, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
