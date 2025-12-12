import tkinter as tk
import random
from collections import Counter

# ----------------- Config -----------------

GAME_TITLE = "High Stakes v0.5"

SUITS = ['♠', '♥', '♣', '♦']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14 for ordering only

HAND_MULTIPLIERS = {
    "High Card": 1,
    "Pair": 1.5,
    "Two Pair": 2,
    "Three of a Kind": 2.5,
    "Straight": 3,
    "Flush": 3.5,
    "Full House": 4,
    "Four of a Kind": 4.5,
    "Straight Flush": 5,
    "Five of a Kind": 6,
    "No Cards": 0,
}

HAND_SIZE = 10                # start and maintain 10 cards in hand for this build
CARDS_PER_PAGE = 8
JOKERS_PER_PAGE = 8

# Shared card/joker/deck geometry
CARD_WIDTH = 80
CARD_HEIGHT = 120
CARD_SPACING = 15
LEFT_MARGIN = 40

TOOLTIP_DELAY_MS = 1500


def card_points(rank: str) -> int:
    """Point values: 2–9 => 2–9, 10/J/Q/K => 10, A => 15."""
    if rank == 'A':
        return 15
    if rank in ['10', 'J', 'Q', 'K']:
        return 10
    return int(rank)


class HighStakesGame:
    def __init__(self, root):
        self.root = root
        self.root.title(GAME_TITLE)
        self.canvas_width = 900
        self.canvas_height = 600

        self.canvas = tk.Canvas(
            root,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#202020"
        )
        self.canvas.pack()

        # Game state
        self.full_deck_size = len(SUITS) * len(RANKS)
        self.deck = []
        self.cards_state = []   # canonical hand: list of {rank, suit, selected}
        self.hand_visuals = []  # visuals for current page
        self.card_page = 0
        self.total_score = 0
        self.sort_mode = "rank"  # "rank" or "suit"

        # Joker state
        self.jokers_state = []   # list of {id, name, text, rarity}
        self.joker_visuals = []  # visuals for current joker page
        self.joker_page = 0

        # Deck & stake meta
        self.current_deck_name = "Standard Deck"
        self.deck_modifiers_text = "No deck modifiers yet."
        self.current_stake_name = "White"
        self.current_stake_info = {
            "base_score_req": 100,
            "score_growth": 10,
            "base_mult": 1.5,
            "mult_growth": 0.0,
        }

        # Deck drawing bounds for hit detection
        self.deck_bounds = None

        # Overlay state
        self.deck_overlay_visible = False

        # Drag selection state
        self.drag_start = None
        self.drag_rect_id = None
        self.dragging = False

        # Tooltip state
        self.tooltip_after_id = None
        self.tooltip_window = None
        self.tooltip_target = None  # ("card", idx) or ("joker", idx) or ("deck", None)
        self.last_mouse_pos = (0, 0)

        # UI elements
        self.setup_ui()

        # Setup deck, hand, jokers
        self.start_new_run()

    # ----------------- UI Setup -----------------

    def setup_ui(self):
        # Top-left: total score only
        self.total_score_label = tk.Label(
            self.root,
            text="Total Score: 0",
            fg="white",
            bg="#202020",
            font=("Arial", 12, "bold")
        )
        self.total_score_label.place(x=10, y=10)

        # Left side: Last turn info
        self.last_turn_title = tk.Label(
            self.root,
            text="Last Turn",
            fg="white",
            bg="#202020",
            font=("Arial", 12, "bold")
        )
        self.last_turn_title.place(x=10, y=60)

        self.last_turn_detail = tk.Label(
            self.root,
            text="(none yet)",
            fg="white",
            bg="#202020",
            font=("Consolas", 10),
            justify="left"
        )
        self.last_turn_detail.place(x=10, y=85)

        # Center: current hand calculations
        self.current_calc_label = tk.Label(
            self.root,
            text="Select cards to see hand calculations.",
            fg="white",
            bg="#202020",
            font=("Consolas", 11),
            justify="center"
        )
        self.current_calc_label.place(
            x=self.canvas_width // 2 - 260,
            y=60,
            width=520
        )

        # Bottom-left: status/info
        self.info_label = tk.Label(
            self.root,
            text="Select up to 5 cards to see the current hand.",
            fg="white",
            bg="#202020"
        )
        self.info_label.place(x=10, y=self.canvas_height - 30)

        # Buttons: Play / Discard + Sort buttons
        self.play_button = tk.Button(self.root, text="Play", command=self.play_hand, width=10)
        self.discard_button = tk.Button(self.root, text="Discard", command=self.discard_selected, width=10)
        self.sort_rank_button = tk.Button(self.root, text="Sort: Rank", command=self.sort_by_rank, width=10)
        self.sort_suit_button = tk.Button(self.root, text="Sort: Suit", command=self.sort_by_suit, width=10)

        center_x = self.canvas_width // 2
        base_y = self.canvas_height - 60
        spacing = 100

        self.play_button.place(x=center_x - spacing - 50, y=base_y)
        self.discard_button.place(x=center_x - 50, y=base_y)
        self.sort_rank_button.place(x=center_x + spacing - 50, y=base_y)
        self.sort_suit_button.place(x=center_x + 2 * spacing - 50, y=base_y)

        # Paging buttons for cards
        self.card_page_left_button = tk.Button(self.root, text="◀", command=self.prev_card_page, width=3)
        self.card_page_right_button = tk.Button(self.root, text="▶", command=self.next_card_page, width=3)

        # Paging buttons for jokers
        self.joker_page_left_button = tk.Button(self.root, text="◀", command=self.prev_joker_page, width=3)
        self.joker_page_right_button = tk.Button(self.root, text="▶", command=self.next_joker_page, width=3)

        # Canvas bindings
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", self.on_mouse_leave)

    # ----------------- Run setup -----------------

    def start_new_run(self):
        self.total_score = 0
        self.total_score_label.config(text="Total Score: 0")
        self.cards_state = []
        self.hand_visuals = []
        self.jokers_state = []
        self.joker_visuals = []
        self.card_page = 0
        self.joker_page = 0

        self.create_deck()
        self.shuffle_deck()
        self.draw_initial_hand()
        self.create_default_jokers()
        self.rebuild_hand()
        self.rebuild_jokers()
        self.draw_deck_display()
        self.update_current_calc_display()

    # ----------------- Deck & Drawing -----------------

    def create_deck(self):
        self.deck = [(rank, suit) for suit in SUITS for rank in RANKS]

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def draw_cards_from_deck(self, n):
        drawn = []
        for _ in range(n):
            if not self.deck:
                break
            drawn.append(self.deck.pop())
        return drawn

    def draw_initial_hand(self):
        cards = self.draw_cards_from_deck(HAND_SIZE)
        self.cards_state = [{"rank": r, "suit": s, "selected": False} for (r, s) in cards]
        self.card_page = 0

    def card_positions(self, count):
        # shared sizing, left aligned row
        total_width = count * CARD_WIDTH + (count - 1) * CARD_SPACING
        start_x = LEFT_MARGIN
        y_base = self.canvas_height - CARD_HEIGHT - 110
        return CARD_WIDTH, CARD_HEIGHT, CARD_SPACING, start_x, y_base

    def create_card_visual(self, x, y, w, h, rank, suit, selected, idx):
        rect_id = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill="#303030",
            outline="white",
            width=2
        )
        text_id = self.canvas.create_text(
            x + w / 2,
            y + h / 2,
            text=f"{rank}{suit}",
            fill="white",
            font=("Arial", 16, "bold")
        )
        if selected:
            dy = -20
            self.canvas.move(rect_id, 0, dy)
            self.canvas.move(text_id, 0, dy)
            y += dy

        return {
            "rank": rank,
            "suit": suit,
            "rect": rect_id,
            "text": text_id,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "selected": selected,
            "base_y": y if not selected else y + 20,
            "idx": idx,
        }

    def rebuild_hand(self):
        """Recreate all card visuals for the current card page from cards_state."""
        # Sort canonical state
        if self.sort_mode == "rank":
            self.cards_state = sorted(
                self.cards_state,
                key=lambda c: RANK_VALUES[c["rank"]],
                reverse=True
            )
        elif self.sort_mode == "suit":
            self.cards_state = sorted(
                self.cards_state,
                key=lambda c: (SUITS.index(c["suit"]), -RANK_VALUES[c["rank"]])
            )

        # Compute paging
        total_cards = len(self.cards_state)
        if total_cards == 0:
            total_pages = 1
        else:
            total_pages = (total_cards + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE

        # Clamp page
        if self.card_page >= total_pages:
            self.card_page = total_pages - 1
        if self.card_page < 0:
            self.card_page = 0

        start = self.card_page * CARDS_PER_PAGE
        end = min(start + CARDS_PER_PAGE, total_cards)
        visible = self.cards_state[start:end]

        # Clear old visuals
        for card in self.hand_visuals:
            self.canvas.delete(card["rect"])
            self.canvas.delete(card["text"])
        self.hand_visuals.clear()

        if visible:
            card_width, card_height, spacing, start_x, y_base = self.card_positions(len(visible))

            for i, c in enumerate(visible):
                x = start_x + i * (card_width + spacing)
                card_v = self.create_card_visual(
                    x, y_base, card_width, card_height,
                    c["rank"], c["suit"], c["selected"], idx=start + i
                )
                self.hand_visuals.append(card_v)

        self.update_card_paging_buttons(total_pages)
        self.draw_deck_display()
        self.update_current_calc_display()

    def draw_deck_display(self):
        # Clear previous deck visuals
        self.canvas.delete("deck")

        deck_w = CARD_WIDTH
        deck_h = CARD_HEIGHT
        deck_x = self.canvas_width - deck_w - LEFT_MARGIN
        deck_y = 20

        # Main deck rectangle
        self.canvas.create_rectangle(
            deck_x, deck_y, deck_x + deck_w, deck_y + deck_h,
            fill="#303030", outline="white", width=2, tags="deck"
        )
        # A "stack" behind it
        self.canvas.create_rectangle(
            deck_x + 5, deck_y - 5, deck_x + deck_w + 5, deck_y + deck_h - 5,
            outline="white", tags="deck"
        )
        # Label
        self.canvas.create_text(
            deck_x + deck_w / 2,
            deck_y + 25,
            text="Deck",
            fill="white",
            font=("Arial", 12, "bold"),
            tags="deck"
        )
        # Card count (remaining / full)
        self.canvas.create_text(
            deck_x + deck_w / 2,
            deck_y + deck_h - 20,
            text=f"{len(self.deck)}/{self.full_deck_size}",
            fill="white",
            font=("Arial", 10),
            tags="deck"
        )

        self.deck_bounds = (deck_x, deck_y, deck_x + deck_w, deck_y + deck_h)

    # ----------------- Jokers -----------------

    def create_default_jokers(self):
        self.jokers_state = [
            {
                "id": "regular_joker",
                "name": "Regular Joker",
                "text": "+10 points each hand",
                "rarity": "Common",
            },
            {
                "id": "money_doubler",
                "name": "Money Doubler",
                "text": "Pairs have double multiplier",
                "rarity": "Uncommon",
            },
        ]
        self.joker_page = 0

    def joker_positions(self, count):
        # Same sizing and left margin as cards, different vertical position
        total_width = count * CARD_WIDTH + (count - 1) * CARD_SPACING
        start_x = LEFT_MARGIN
        y_base = 230
        return CARD_WIDTH, CARD_HEIGHT, CARD_SPACING, start_x, y_base

    def rarity_outline_color(self, rarity):
        return {
            "Common": "white",
            "Uncommon": "green",
            "Rare": "red",
            "Epic": "purple",
            "Legendary": "orange",
            "Mythical": "gold",
        }.get(rarity, "white")

    def create_joker_visual(self, x, y, w, h, joker):
        rect_id = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill="#303030",
            outline=self.rarity_outline_color(joker.get("rarity", "Common")),
            width=2,
            tags="joker"
        )
        # Only show name on the card; description is in tooltip
        text = joker['name']
        text_id = self.canvas.create_text(
            x + w / 2,
            y + h / 2,
            text=text,
            fill="white",
            font=("Arial", 10, "bold"),
            width=w - 10,
            tags="joker"
        )
        return {
            "rect": rect_id,
            "text": text_id,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
        }

    def rebuild_jokers(self):
        # Compute paging
        total_jokers = len(self.jokers_state)
        if total_jokers == 0:
            total_pages = 1
        else:
            total_pages = (total_jokers + JOKERS_PER_PAGE - 1) // JOKERS_PER_PAGE

        if self.joker_page >= total_pages:
            self.joker_page = total_pages - 1
        if self.joker_page < 0:
            self.joker_page = 0

        start = self.joker_page * JOKERS_PER_PAGE
        end = min(start + JOKERS_PER_PAGE, total_jokers)
        visible = self.jokers_state[start:end]

        # Clear old joker visuals
        for j in self.joker_visuals:
            self.canvas.delete(j["rect"])
            self.canvas.delete(j["text"])
        self.joker_visuals.clear()

        if visible:
            card_width, card_height, spacing, start_x, y_base = self.joker_positions(len(visible))
            for i, j in enumerate(visible):
                x = start_x + i * (card_width + spacing)
                jv = self.create_joker_visual(x, y_base, card_width, card_height, j)
                self.joker_visuals.append(jv)

        self.update_joker_paging_buttons(total_pages)

    # ----------------- Paging Buttons -----------------

    def update_card_paging_buttons(self, total_pages):
        # Place under leftmost/rightmost visible cards
        if total_pages <= 1 or not self.hand_visuals:
            self.card_page_left_button.place_forget()
            self.card_page_right_button.place_forget()
            return

        first = self.hand_visuals[0]
        last = self.hand_visuals[-1]
        y = first["y"] + first["h"] + 10

        # Left arrow
        if self.card_page > 0:
            x_left = first["x"] + first["w"] / 2 - 15
            self.card_page_left_button.place(x=int(x_left), y=int(y))
        else:
            self.card_page_left_button.place_forget()

        # Right arrow
        if self.card_page < total_pages - 1:
            x_right = last["x"] + last["w"] / 2 - 15
            self.card_page_right_button.place(x=int(x_right), y=int(y))
        else:
            self.card_page_right_button.place_forget()

    def update_joker_paging_buttons(self, total_pages):
        if total_pages <= 1 or not self.joker_visuals:
            self.joker_page_left_button.place_forget()
            self.joker_page_right_button.place_forget()
            return

        first = self.joker_visuals[0]
        last = self.joker_visuals[-1]
        y = first["y"] + first["h"] + 10

        # Left arrow
        if self.joker_page > 0:
            x_left = first["x"] + first["w"] / 2 - 15
            self.joker_page_left_button.place(x=int(x_left), y=int(y))
        else:
            self.joker_page_left_button.place_forget()

        # Right arrow
        if self.joker_page < total_pages - 1:
            x_right = last["x"] + last["w"] / 2 - 15
            self.joker_page_right_button.place(x=int(x_right), y=int(y))
        else:
            self.joker_page_right_button.place_forget()

    def next_card_page(self):
        self.card_page += 1
        self.rebuild_hand()

    def prev_card_page(self):
        self.card_page -= 1
        self.rebuild_hand()

    def next_joker_page(self):
        self.joker_page += 1
        self.rebuild_jokers()

    def prev_joker_page(self):
        self.joker_page -= 1
        self.rebuild_jokers()

    # ----------------- Interaction -----------------

    def on_left_press(self, event):
        if self.deck_overlay_visible:
            # Click closes overlay
            self.hide_deck_overlay()
            return

        self.drag_start = (event.x, event.y)
        self.dragging = False
        self.last_mouse_pos = (event.x, event.y)
        self.cancel_tooltip()

    def on_left_drag(self, event):
        if self.drag_start is None:
            return
        self.dragging = True
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y

        if self.drag_rect_id is not None:
            self.canvas.delete(self.drag_rect_id)
        self.drag_rect_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline="yellow",
            dash=(3, 3)
        )

    def on_left_release(self, event):
        if self.drag_rect_id is not None:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None

        if self.drag_start is None:
            return

        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        self.drag_start = None

        # If drag distance is small, treat as simple click
        if not self.dragging or (abs(x1 - x0) < 5 and abs(y1 - y0) < 5):
            # Simple click: deck or card
            if self.is_point_in_deck(event.x, event.y):
                self.toggle_deck_overlay()
            else:
                self.handle_card_click(event.x, event.y)
        else:
            # Drag-select cards
            self.handle_drag_select(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

        self.dragging = False

    def on_right_click(self, event):
        # Right click deselects all cards
        for c in self.cards_state:
            c["selected"] = False
        self.rebuild_hand()
        self.info_label.config(text="Cleared all selections.")

    def handle_card_click(self, x, y):
        clicked_index = None
        for i, card in enumerate(self.hand_visuals):
            cx, cy, w, h = card["x"], card["y"], card["w"], card["h"]
            if cx <= x <= cx + w and cy <= y <= cy + h:
                clicked_index = i
                break

        if clicked_index is not None:
            self.toggle_card_selection(clicked_index)

    def handle_drag_select(self, x0, y0, x1, y1):
        # Select all cards whose rectangles intersect the drag box, up to 5 total
        max_selectable = 5
        already_selected = sum(1 for c in self.cards_state if c["selected"])

        for card_v in self.hand_visuals:
            cx0, cy0 = card_v["x"], card_v["y"]
            cx1, cy1 = cx0 + card_v["w"], cy0 + card_v["h"]

            intersects = not (cx1 < x0 or cx0 > x1 or cy1 < y0 or cy0 > y1)
            if not intersects:
                continue

            global_idx = card_v["idx"]
            card_state = self.cards_state[global_idx]

            if not card_state["selected"] and already_selected < max_selectable:
                card_state["selected"] = True
                already_selected += 1

        self.rebuild_hand()
        self.info_label.config(text="Drag-selected cards (max 5).")

    def on_mouse_move(self, event):
        self.last_mouse_pos = (event.x, event.y)
        self.schedule_tooltip(event.x, event.y)

    def on_mouse_leave(self, event):
        self.cancel_tooltip()

    def toggle_card_selection(self, visible_index):
        card_v = self.hand_visuals[visible_index]
        global_idx = card_v["idx"]
        card_state = self.cards_state[global_idx]

        max_selectable = 5

        total_selected = sum(1 for c in self.cards_state if c["selected"])
        if not card_state["selected"]:
            if total_selected >= max_selectable:
                self.info_label.config(text=f"Max {max_selectable} cards can be selected.")
                return
            card_state["selected"] = True
            card_v["selected"] = True
            dy = -20
        else:
            card_state["selected"] = False
            card_v["selected"] = False
            dy = 20

        self.canvas.move(card_v["rect"], 0, dy)
        self.canvas.move(card_v["text"], 0, dy)
        card_v["y"] += dy

        self.info_label.config(text="Select up to 5 cards to see the current hand.")
        self.update_current_calc_display()

    def get_selected_cards(self):
        return [(c["rank"], c["suit"]) for c in self.cards_state if c["selected"]]

    # ----------------- Tooltip logic -----------------

    def schedule_tooltip(self, x, y):
        # Determine what we're hovering over
        target = self.get_hover_target(x, y)

        if target == self.tooltip_target:
            return  # unchanged; existing timer is fine

        self.tooltip_target = target
        self.cancel_tooltip()

        if target is not None:
            self.tooltip_after_id = self.root.after(TOOLTIP_DELAY_MS, self.show_tooltip)

    def cancel_tooltip(self):
        if self.tooltip_after_id is not None:
            self.root.after_cancel(self.tooltip_after_id)
            self.tooltip_after_id = None
        if self.tooltip_window is not None:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def get_hover_target(self, x, y):
        # Check deck first
        if self.is_point_in_deck(x, y):
            return ("deck", None)

        # Check jokers
        for i, jv in enumerate(self.joker_visuals):
            if jv["x"] <= x <= jv["x"] + jv["w"] and jv["y"] <= y <= jv["y"] + jv["h"]:
                return ("joker", i)

        # Check cards
        for i, cv in enumerate(self.hand_visuals):
            if cv["x"] <= x <= cv["x"] + cv["w"] and cv["y"] <= y <= cv["y"] + cv["h"]:
                return ("card", i)

        return None

    def show_tooltip(self):
        if self.tooltip_target is None:
            return

        x, y = self.last_mouse_pos
        kind, idx = self.tooltip_target

        if kind == "deck":
            text = self.deck_tooltip_text()
        elif kind == "joker":
            text = self.joker_tooltip_text(idx)
        elif kind == "card":
            text = self.card_tooltip_text(idx)
        else:
            return

        # Create a small toplevel window near the cursor
        self.tooltip_window = tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x + 20}+{y + 20}")
        label = tk.Label(tw, text=text, justify="left",
                         background="#404040", foreground="white",
                         relief="solid", borderwidth=1,
                         font=("Consolas", 9))
        label.pack(ipadx=4, ipady=2)

    def deck_tooltip_text(self):
        stake = self.current_stake_info
        deck_line = f"{self.current_deck_name}: {self.deck_modifiers_text}"
        stake_line = (f"{self.current_stake_name} Stake · "
                      f"Base req {stake['base_score_req']}, +{stake['score_growth']} per round; "
                      f"Base mult {stake['base_mult']}, +{stake['mult_growth']} per round")
        return deck_line + "\n" + stake_line

    def joker_tooltip_text(self, idx):
        j = self.jokers_state[self.joker_page * JOKERS_PER_PAGE + idx]
        lines = [j["name"], f"[{j.get('rarity', 'Common')} Joker]", j["text"]]
        return "\n".join(lines)

    def card_tooltip_text(self, idx):
        cv = self.hand_visuals[idx]
        r, s = cv["rank"], cv["suit"]
        value = card_points(r)
        return f"{r}{s}\n+{value} Score"

    # ----------------- Deck overlay (stats & probabilities) -----------------

    def is_point_in_deck(self, x, y):
        if self.deck_bounds is None:
            return False
        x0, y0, x1, y1 = self.deck_bounds
        return x0 <= x <= x1 and y0 <= y <= y1

    def toggle_deck_overlay(self):
        if self.deck_overlay_visible:
            self.hide_deck_overlay()
        else:
            self.show_deck_overlay()

    def show_deck_overlay(self):
        self.deck_overlay_visible = True
        self.canvas.delete("deck_overlay")

        # Background
        margin = 60
        x0, y0 = margin, margin
        x1, y1 = self.canvas_width - margin, self.canvas_height - margin
        self.canvas.create_rectangle(
            x0, y0, x1, y1,
            fill="#101010",
            outline="white",
            width=2,
            tags="deck_overlay"
        )

        total = len(self.deck)
        suits_count = Counter(s for (_, s) in self.deck)
        ranks_count = Counter(r for (r, _) in self.deck)

        # Title
        self.canvas.create_text(
            (x0 + x1) / 2,
            y0 + 20,
            text="Deck Overview",
            fill="white",
            font=("Arial", 16, "bold"),
            tags="deck_overlay"
        )

        # Summary
        self.canvas.create_text(
            x0 + 10,
            y0 + 50,
            anchor="w",
            text=f"Cards remaining: {total}/{self.full_deck_size}",
            fill="white",
            font=("Consolas", 11),
            tags="deck_overlay"
        )

        # Suits
        suit_lines = []
        for s in SUITS:
            c = suits_count.get(s, 0)
            p = (c / total * 100) if total > 0 else 0.0
            suit_lines.append(f"{s}: {c} ({p:.1f}%)")
        self.canvas.create_text(
            x0 + 10,
            y0 + 80,
            anchor="nw",
            text="Suits (probability next draw):\n" + "\n".join(suit_lines),
            fill="white",
            font=("Consolas", 10),
            tags="deck_overlay"
        )

        # Ranks in two columns
        rank_lines_left = []
        rank_lines_right = []
        for i, r in enumerate(RANKS):
            c = ranks_count.get(r, 0)
            p = (c / total * 100) if total > 0 else 0.0
            line = f"{r}: {c} ({p:.1f}%)"
            if i < len(RANKS) / 2:
                rank_lines_left.append(line)
            else:
                rank_lines_right.append(line)

        self.canvas.create_text(
            x0 + 10,
            y0 + 160,
            anchor="nw",
            text="Ranks (probability next draw):\n" + "\n".join(rank_lines_left),
            fill="white",
            font=("Consolas", 10),
            tags="deck_overlay"
        )
        self.canvas.create_text(
            (x0 + x1) / 2,
            y0 + 160,
            anchor="nw",
            text="\n".join(rank_lines_right),
            fill="white",
            font=("Consolas", 10),
            tags="deck_overlay"
        )

        # Close hint
        self.canvas.create_text(
            (x0 + x1) / 2,
            y1 - 20,
            text="Click anywhere to close",
            fill="gray",
            font=("Consolas", 9, "italic"),
            tags="deck_overlay"
        )

    def hide_deck_overlay(self):
        self.deck_overlay_visible = False
        self.canvas.delete("deck_overlay")

    # ----------------- Hand Evaluation -----------------

    def evaluate_hand(self, cards):
        """
        Evaluate the selected cards.
        Returns: (hand_name, scoring_cards, base_sum, base_mult, final_mult, add_bonus, total_score)
        scoring_cards is the subset of cards that actually score (e.g. pairs only, no kicker).
        """
        if not cards:
            return "No Cards", [], 0, 0, 0, 0, 0

        ranks = [c[0] for c in cards]
        suits = [c[1] for c in cards]

        counts = Counter(ranks)
        count_values = sorted(counts.values(), reverse=True)

        is_flush, flush_suit = self.check_flush(suits, cards)
        is_straight, straight_ranks = self.check_straight(ranks)

        # Determine hand type and scoring subset
        hand_name = "High Card"
        scoring_cards = []

        # Five of a kind (kept for completeness)
        if max(count_values) == 5:
            hand_name = "Five of a Kind"
            rank5 = max(counts, key=lambda r: counts[r])
            scoring_cards = [c for c in cards if c[0] == rank5][:5]

        # Straight flush
        elif is_flush and is_straight and len(straight_ranks) == 5 and len(cards) >= 5:
            hand_name = "Straight Flush"
            scoring_cards = self.pick_cards_for_ranks(cards, straight_ranks, flush_suit)

        # Four of a kind
        elif max(count_values) == 4:
            hand_name = "Four of a Kind"
            rank4 = max(counts, key=lambda r: counts[r] if counts[r] == 4 else 0)
            scoring_cards = [c for c in cards if c[0] == rank4][:4]

        # Full house
        elif 3 in count_values and 2 in count_values:
            hand_name = "Full House"
            three_ranks = [r for r, c in counts.items() if c >= 3]
            two_ranks = [r for r, c in counts.items() if c >= 2 and r not in three_ranks]
            if three_ranks and two_ranks:
                three_rank = max(three_ranks, key=lambda r: RANK_VALUES[r])
                two_rank = max(two_ranks, key=lambda r: RANK_VALUES[r])
                scoring_cards = (
                    [c for c in cards if c[0] == three_rank][:3] +
                    [c for c in cards if c[0] == two_rank][:2]
                )
            else:
                hand_name = "Three of a Kind"
                three_rank = max(three_ranks, key=lambda r: RANK_VALUES[r])
                scoring_cards = [c for c in cards if c[0] == three_rank][:3]

        # Flush
        elif is_flush and len(cards) >= 5:
            hand_name = "Flush"
            scoring_cards = [c for c in cards if c[1] == flush_suit][:5]

        # Straight
        elif is_straight and len(straight_ranks) == 5 and len(cards) >= 5:
            hand_name = "Straight"
            scoring_cards = self.pick_cards_for_ranks(cards, straight_ranks)

        # Three of a kind
        elif 3 in count_values:
            hand_name = "Three of a Kind"
            three_rank = max([r for r, c in counts.items() if c == 3], key=lambda r: RANK_VALUES[r])
            scoring_cards = [c for c in cards if c[0] == three_rank][:3]

        # Two pair
        elif count_values.count(2) >= 2:
            hand_name = "Two Pair"
            pair_ranks = [r for r, c in counts.items() if c >= 2]
            pair_ranks.sort(key=lambda r: RANK_VALUES[r], reverse=True)
            top_two = pair_ranks[:2]
            scoring_cards = []
            for pr in top_two:
                scoring_cards.extend([c for c in cards if c[0] == pr][:2])

        # Pair
        elif 2 in count_values:
            hand_name = "Pair"
            pair_rank = max([r for r, c in counts.items() if c == 2], key=lambda r: RANK_VALUES[r])
            scoring_cards = [c for c in cards if c[0] == pair_rank][:2]

        # High card
        else:
            hand_name = "High Card"
            highest_rank = max(ranks, key=lambda r: RANK_VALUES[r])
            for c in cards:
                if c[0] == highest_rank:
                    scoring_cards = [c]
                    break

        base_sum = sum(card_points(r) for (r, _) in scoring_cards)
        base_mult = HAND_MULTIPLIERS.get(hand_name, 1)

        final_mult, add_bonus = self.apply_jokers(hand_name, base_sum, base_mult)
        total = int((base_sum + add_bonus) * final_mult)

        return hand_name, scoring_cards, base_sum, base_mult, final_mult, add_bonus, total

    def check_flush(self, suits, cards):
        suit_counts = Counter(suits)
        for suit, count in suit_counts.items():
            if count >= 5 and len(cards) >= 5:
                return True, suit
        return False, None

    def check_straight(self, ranks):
        values = sorted({RANK_VALUES[r] for r in ranks})
        if len(values) < 5:
            return False, []

        # normal straights
        for i in range(len(values) - 4):
            window = values[i:i+5]
            if window[-1] - window[0] == 4 and len(set(window)) == 5:
                straight_ranks = []
                for v in window:
                    for r in RANKS:
                        if RANK_VALUES[r] == v:
                            straight_ranks.append(r)
                            break
                return True, straight_ranks

        # wheel A-2-3-4-5
        vals_set = set(values)
        wheel_vals = {RANK_VALUES['A'], RANK_VALUES['2'], RANK_VALUES['3'],
                      RANK_VALUES['4'], RANK_VALUES['5']}
        if wheel_vals.issubset(vals_set):
            return True, ['2', '3', '4', '5', 'A']

        return False, []

    def pick_cards_for_ranks(self, cards, ranks_needed, flush_suit=None):
        picked = []
        remaining = list(cards)
        for r in ranks_needed:
            for c in remaining:
                if c[0] == r and (flush_suit is None or c[1] == flush_suit):
                    picked.append(c)
                    remaining.remove(c)
                    break
        return picked

    def apply_jokers(self, hand_name, base_sum, base_mult):
        """
        Apply joker effects following order:
        Additions -> Multipliers.
        Returns (final_multiplier, additive_bonus).
        """
        add_bonus = 0.0
        mult_factor = 1.0

        for j in self.jokers_state:
            if j["id"] == "regular_joker":
                # +10 points BEFORE multipliers
                add_bonus += 10
            elif j["id"] == "money_doubler" and hand_name == "Pair":
                mult_factor *= 2

        final_mult = base_mult * mult_factor
        return final_mult, add_bonus

    def update_current_calc_display(self):
        selected = self.get_selected_cards()
        if not selected:
            self.current_calc_label.config(
                text="Select cards to see hand calculations."
            )
            return

        (hand_name, scoring_cards, base_sum,
         base_mult, final_mult, add_bonus, total) = self.evaluate_hand(selected)

        scoring_ranks = " ".join(r for (r, _) in scoring_cards)
        scoring_suits = " ".join(s for (_, s) in scoring_cards)

        calc_text = (
            f"Current Hand: {hand_name}\n"
            f"Scoring Ranks: {scoring_ranks}\n"
            f"Scoring Suits: {scoring_suits}\n"
            f"Base sum of scoring cards = {base_sum}\n"
            f"Base multiplier = {base_mult}x\n"
            f"Additive joker bonus = {add_bonus}\n"
            f"Final multiplier after jokers = {final_mult}x\n"
            f"Score = ({base_sum} + {add_bonus}) × {final_mult} = {total}"
        )
        self.current_calc_label.config(text=calc_text)

    # ----------------- Play / Discard -----------------

    def play_hand(self):
        selected_cards = self.get_selected_cards()
        if not selected_cards:
            self.info_label.config(text="Select at least one card before playing.")
            return

        (hand_name, scoring_cards, base_sum,
         base_mult, final_mult, add_bonus, total) = self.evaluate_hand(selected_cards)

        self.total_score += total
        self.total_score_label.config(text=f"Total Score: {self.total_score}")

        scoring_ranks = " ".join(r for (r, _) in scoring_cards)
        scoring_suits = " ".join(s for (_, s) in scoring_cards)
        last_text = (
            f"{hand_name}\n"
            f"Scoring Ranks: {scoring_ranks}\n"
            f"Scoring Suits: {scoring_suits}\n"
            f"Base sum = {base_sum}\n"
            f"Base mult = {base_mult}x\n"
            f"Add bonus = {add_bonus}\n"
            f"Final mult = {final_mult}x\n"
            f"Turn Score = {total}"
        )
        self.last_turn_detail.config(text=last_text)

        self.info_label.config(text=f"Played a {hand_name}! (+{total} points)")

        new_state = []
        for c in self.cards_state:
            if c["selected"]:
                continue
            new_state.append({"rank": c["rank"], "suit": c["suit"], "selected": False})

        needed = HAND_SIZE - len(new_state)
        new_cards = self.draw_cards_from_deck(needed)
        for (r, s) in new_cards:
            new_state.append({"rank": r, "suit": s, "selected": False})

        self.cards_state = new_state
        self.rebuild_hand()

    def discard_selected(self):
        selected_count = sum(1 for c in self.cards_state if c["selected"])
        if selected_count == 0:
            self.info_label.config(text="Select one or more cards to discard.")
            return

        new_state = []
        for c in self.cards_state:
            if c["selected"]:
                continue
            new_state.append({"rank": c["rank"], "suit": c["suit"], "selected": False})

        needed = HAND_SIZE - len(new_state)
        new_cards = self.draw_cards_from_deck(needed)
        for (r, s) in new_cards:
            new_state.append({"rank": r, "suit": s, "selected": False})

        self.cards_state = new_state
        self.info_label.config(text="Discarded selected cards and redrew (or deck ran out).")
        self.rebuild_hand()

    # ----------------- Sorting -----------------

    def sort_by_rank(self):
        self.sort_mode = "rank"
        for c in self.cards_state:
            c["selected"] = False
        self.rebuild_hand()
        self.info_label.config(text="Hand sorted by rank (high to low).")

    def sort_by_suit(self):
        self.sort_mode = "suit"
        for c in self.cards_state:
            c["selected"] = False
        self.rebuild_hand()
        self.info_label.config(text="Hand sorted by suit, then rank.")


if __name__ == "__main__":
    root = tk.Tk()
    app = HighStakesGame(root)
    root.mainloop()
