"""Controls / help cheatsheet — written for non-technical users."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame


_SECTIONS = [
    ("👋  Welcome", [
        ("What is this panel?",
         "The pink/red NoMansMovies bar that floats over your game. It controls "
         "everything else — your video, your friends list, your sources tab, etc. "
         "If it's gone, look at your Windows taskbar (bottom of the screen) for "
         "the NoMansMovies icon and click it."),
    ]),
    ("🎮  Keyboard shortcuts", [
        ("Press 9 three times fast",
         "Quick cinema mode: hides everything except the video. Press 9 three "
         "times again to bring everything back."),
        ("Esc",
         "Exit fullscreen video."),
    ]),
    ("👤  Profile…",
        [("What it does",
          "Opens a window with TWO sides: Profile (avatar, username, bio, link "
          "Discord, logout) and Appearance (colors, fonts, video border, default "
          "layout)."),
         ("How to close it",
          "Click the ✕ in its title bar, OR click Show All to bring it back later "
          "if you ever lose it."),
        ]),
    ("⊕  Recenter video",
        [("What it does",
          "If your video panel ended up off-screen or weirdly sized, click this. "
          "It snaps the video back to a centered, default-sized window."),
        ]),
    ("⟳  Layout: ____",
        [("What it does",
          "Cycles through layout PRESETS. Click once to switch to the next one. "
          "Built-in presets: Default (everything shown), Movie + Sources, Movie "
          "only. Any Custom layouts you save will also be in this cycle."),
         ("The label on the button",
          "Shows the layout you are CURRENTLY using."),
        ]),
    ("💾  Save Custom Layout",
        [("What it does",
          "Captures the current position, size, and minimized state of every "
          "floating panel and saves it as a new entry (Custom 1, Custom 2, …). "
          "It then becomes part of the ⟳ Layout cycle so you can jump back to it "
          "anytime."),
         ("Tip",
          "Arrange the panels exactly how you like them first, then click this. "
          "You can save up to 9 custom layouts."),
        ]),
    ("👁  Show All",
        [("What it does",
          "Brings every hidden floating panel back into view. Useful if you "
          "accidentally ✕'d the Sources or Watch panel and want them back. "
          "Does NOT change their positions — they reappear where they were."),
        ]),
    ("↺  Restore All Panels",
        [("What it does",
          "Resets EVERY floating panel to its default position and size. Use this "
          "when you've made a mess and just want a clean starting layout."),
        ]),
    ("—  Minimize All Tabs",
        [("What it does",
          "Hides every NoMansMovies window (video, friends, controls bar, "
          "everything). The app stays running — it just gets out of your way."),
         ("How to bring it back",
          "Look at the Windows taskbar at the bottom of your screen. The "
          "NoMansMovies icon appears there as a minimized window. Click that "
          "icon and all your panels come back exactly where they were."),
         ("Why use this",
          "When you want a clean screen for a moment but don't want to close and "
          "re-open the app."),
        ]),
    ("Opacity slider",
        [("What it does",
          "Drag right = panels solid. Drag left = panels see-through, so you "
          "can read your game through them."),
         ("Important",
          "The video player is ALWAYS fully visible — only the other panels get "
          "transparent. That way your movie never looks washed-out."),
        ]),
    ("?  Controls",
        [("What it does", "Opens this guide you're reading right now."),
        ]),
    ("🎬  Floating panel basics", [
        ("Move a panel",
         "Click and drag the title strip at the top of any panel."),
        ("Resize a panel",
         "Hover the edge or corner — the cursor turns into a resize arrow — "
         "then drag."),
        ("— button (panel title)",
         "Minimizes that ONE panel down to just its title strip. Click — again "
         "to restore it."),
        ("✕ button (panel title)",
         "Hides that one panel. Click 👁 Show All to bring it back. The ✕ on the "
         "NoMansMovies controls panel quits the app."),
    ]),
    ("▶  Playback controls", [
        ("⏵ / ⏸",        "Play / Pause"),
        ("⏪ / ⏩",      "Skip backward / forward 10 seconds"),
        ("⏹",           "Stop"),
        ("⏭",           "Next"),
        ("Timeline",     "Drag the slider to jump to a different spot. The numbers "
                          "on either side show where you are and total length."),
        ("🔄 Resync",     "When watching with friends and you got out of sync: "
                          "Host re-broadcasts the current state; Guest snaps to "
                          "the host's latest position."),
        ("⚙",            "Quality (Low to 8K) and aspect ratio."),
        ("⛶",            "Fullscreen video."),
    ]),
    ("👥  Watch together panel", [
        ("Search bar at the top",
         "Type a username and press Enter. Anyone matching shows up below — "
         "click Add to send a friend request."),
        ("Invite",        "Invites this friend to watch the current movie with "
                          "you. Up to 3 people per room."),
        ("DM",            "Opens an iMessage-style chat with this friend right "
                          "inside the panel. The ← arrow returns to the friends "
                          "list."),
        ("Unfriend",      "Removes the friendship."),
        ("Movie invite",  "When a friend invites you, a notification pops up at "
                          "the top-right of your screen. Click Join."),
    ]),
    ("📂  Sources panel (left side)", [
        ("Paste a movie link",
         "Type or paste a direct video URL (mp4, mkv, webm, mov) into the top "
         "text box and click Play. It starts streaming immediately."),
        ("Search YouTube",
         "Type a search term in the YouTube search box and press Enter. Up to "
         "five results appear below with thumbnails and titles. Double-click "
         "any result to start playing it."),
        ("Open a local video",
         "Click 'Open local video…' to pick a file off your computer. It "
         "plays just like any other source."),
        ("Important about local files",
         "Local files cannot be shared with friends — the Invite button is "
         "greyed out. Use a direct link or YouTube if you want to invite "
         "people to watch with you."),
    ]),
    ("👥  Friends panel (in Profile editor)", [
        ("All tab",
         "Every friend you have. A GREEN dot means they're currently using "
         "NoMansMovies. A GREY dot means they're offline."),
        ("Online tab",
         "Only the friends who are using the app right now. Quick way to see "
         "who you could invite."),
        ("Requests tab",
         "Pending friend requests other people sent to YOU. Hit Accept to "
         "become friends, or Decline to ignore."),
        ("Discord tab",
         "Other NoMansMovies users who have linked their Discord account. "
         "Click Add to send them a friend request."),
        ("Search tab",
         "Use the search bar at the top of the panel to find people by "
         "username. Results show here."),
        ("View / Message / Remove",
         "Each friend row has buttons: View their profile, Message them, or "
         "Remove the friendship."),
    ]),
    ("🪟  Resize / move / customize layouts — step by step", [
        ("1. Move panels around",
         "Grab a panel by its title strip at the very top and drag it. The "
         "cursor turns into a 4-way arrow."),
        ("2. Resize panels",
         "Slowly move the mouse to the edge or corner of a panel. The cursor "
         "turns into a resize arrow (↔, ↕, or diagonal). Click and drag to "
         "make the panel bigger or smaller."),
        ("3. Minimize a single panel",
         "Click — in the panel's title strip. The panel shrinks to just its "
         "title bar. Click ▢ in the same spot to restore it."),
        ("4. Hide a single panel",
         "Click ✕ in the panel's title strip. The panel disappears."),
        ("5. Bring a hidden panel back",
         "Click 👁 Show All on the NoMansMovies controls bar."),
        ("6. Save your custom arrangement",
         "Once everything looks how you want, click 💾 Save Custom Layout on "
         "the NoMansMovies controls bar. The layout becomes Custom 1 (or 2, "
         "3, …) and is added to the ⟳ Layout cycle button."),
        ("7. Switch between layouts later",
         "Click ⟳ Layout to cycle through Default → Movie + Sources → Movie "
         "only → Custom 1 → Custom 2 → …"),
        ("8. Reset everything",
         "Click ↺ Restore All Panels to go back to factory defaults."),
    ]),
    ("🎮  Discord", [
        ("Link Discord",  "In the Profile editor. Opens your browser, you "
                          "approve in Discord, and you come back signed in. "
                          "No password is sent."),
        ("Rich Presence", "While Discord is running, your status will say "
                          "'Gaming in NoMansMovies' along with what you're "
                          "watching."),
        ("Online friends",
         "Friends who are currently using NoMansMovies show a green dot. "
         "Friends who aren't show a grey one."),
        ("Logout",
         "In the Profile editor (👤 Profile…) → Logout button. Signs you out "
         "and quits the app. Relaunch to log back in with a different account."),
    ]),
]


class ControlsHelpPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body); lay.setContentsMargins(18, 18, 18, 18); lay.setSpacing(10)

        title = QLabel("Controls & How-To")
        title.setStyleSheet("font-size: 20pt; font-weight: 700;")
        lay.addWidget(title)
        intro = QLabel(
            "Every button on the NoMansMovies controls bar explained in plain English."
        )
        intro.setProperty("muted", True); intro.setWordWrap(True)
        lay.addWidget(intro)

        for heading, rows in _SECTIONS:
            h = QLabel(heading)
            h.setStyleSheet("font-size: 13pt; font-weight: 700; margin-top: 10px;")
            lay.addWidget(h)
            for key, desc in rows:
                r = QLabel(f"<div style='margin-top:4px'><b>{key}</b><br>{desc}</div>")
                r.setWordWrap(True)
                r.setTextFormat(Qt.RichText)
                r.setStyleSheet("padding: 2px 0;")
                lay.addWidget(r)

        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)
