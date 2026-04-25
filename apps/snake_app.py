import random

from gui.core.colors import BLACK, GRAY, GREEN, RED, WHITE, YELLOW
from gui.core.gui import Screen, Widget
from gui.fonts import font10, freesans20
from gui.widgets.label import Label
from input_keys import BLE_KEY_DOWN, BLE_KEY_ENTER, BLE_KEY_LEFT, BLE_KEY_MENU, BLE_KEY_RIGHT, BLE_KEY_UP, GPIO_KEY_ENTER, GPIO_KEY_MENU, GPIO_KEY_NEXT, GPIO_KEY_PREV, KEY_S_PRESSED, KEY_S_RELEASED
from manager import PopApp, exit_app
from utils.trace import DEBUG_INFO, dprint


SNAKE_DEF = {
    "name": "Snake",
    "menu_icon_image": "res/images/snake.png565",
}


class SnakeBoardWidget(Widget):
    def __init__(self, x, y, cell_size, cols, rows, app):
        super().__init__(x, y, cell_size * cols, cell_size * rows)
        self.cell_size = cell_size
        self.cols = cols
        self.rows = rows
        self.app = app

    def _draw_cell(self, draw_ctx, origin_x, origin_y, cell, color, inset=1):
        x = origin_x + cell[0] * self.cell_size + inset
        y = origin_y + cell[1] * self.cell_size + inset
        size = self.cell_size - inset * 2
        if size > 0:
            draw_ctx.fill_rect(x, y, size, size, color)

    def on_draw(self, draw_ctx):
        gr = self.global_rect()
        draw_ctx.fill_rect(gr.x, gr.y, gr.w, gr.h, BLACK)

        for x in range(self.cols + 1):
            px = gr.x + x * self.cell_size
            draw_ctx.vline(px, gr.y, gr.h, GRAY)
        for y in range(self.rows + 1):
            py = gr.y + y * self.cell_size
            draw_ctx.hline(gr.x, py, gr.w, GRAY)

        food = self.app.food
        if food is not None:
            self._draw_cell(draw_ctx, gr.x, gr.y, food, RED, inset=2)

        snake = self.app.snake
        if not snake:
            return

        for segment in snake[1:]:
            self._draw_cell(draw_ctx, gr.x, gr.y, segment, GREEN, inset=2)
        self._draw_cell(draw_ctx, gr.x, gr.y, snake[0], YELLOW, inset=2)


class SnakeApp(PopApp):
    DIR_UP = (0, -1)
    DIR_RIGHT = (1, 0)
    DIR_DOWN = (0, 1)
    DIR_LEFT = (-1, 0)
    TIMER_STEP = 10
    TIMER_EXIT = 11

    def __init__(self):
        super().__init__()
        self.screen = Screen(bgcolor=GRAY)
        self.cols = 15
        self.rows = 15
        self.cell_size = 12
        self.board_x = 30
        self.board_y = 42
        self.step_ms = 220

        self.snake = []
        self.food = None
        self.direction = self.DIR_RIGHT
        self.next_direction = self.DIR_RIGHT
        self.running = False
        self.game_over = False
        self.score = 0

        self.title_label = Label(0, 10, "Snake", freesans20, WHITE, w=self.screen.w, align="center")
        self.score_label = Label(8, 216, "Score: 0", font10, WHITE, w=70)
        self.state_label = Label(78, 216, "ENTER start", font10, WHITE, w=self.screen.w - 86, align="center")
        self.board = SnakeBoardWidget(self.board_x, self.board_y, self.cell_size, self.cols, self.rows, self)

        self.screen.add_list([self.title_label, self.board, self.score_label, self.state_label])
        self.reset_game()

    def reset_game(self):
        mid_x = self.cols // 2
        mid_y = self.rows // 2
        self.snake = [(mid_x, mid_y), (mid_x - 1, mid_y), (mid_x - 2, mid_y)]
        self.direction = self.DIR_RIGHT
        self.next_direction = self.DIR_RIGHT
        self.running = False
        self.game_over = False
        self.score = 0
        self.spawn_food()
        self._update_labels("ENTER start")
        self.board.invalidate()

    def spawn_food(self):
        free_cells = []
        snake_cells = self.snake
        for x in range(self.cols):
            for y in range(self.rows):
                cell = (x, y)
                if cell not in snake_cells:
                    free_cells.append(cell)
        self.food = random.choice(free_cells) if free_cells else None

    def _update_labels(self, state_text=None):
        self.score_label.set_text("Score: {}".format(self.score))
        if state_text is not None:
            self.state_label.set_text(state_text)

    def _turn_left(self):
        direction_order = [self.DIR_UP, self.DIR_LEFT, self.DIR_DOWN, self.DIR_RIGHT]
        idx = direction_order.index(self.direction)
        self.next_direction = direction_order[(idx + 1) % 4]

    def _turn_right(self):
        direction_order = [self.DIR_UP, self.DIR_RIGHT, self.DIR_DOWN, self.DIR_LEFT]
        idx = direction_order.index(self.direction)
        self.next_direction = direction_order[(idx + 1) % 4]

    def _set_absolute_direction(self, new_direction):
        opposite = (-self.direction[0], -self.direction[1])
        if new_direction != opposite:
            self.next_direction = new_direction

    def _step(self):
        if not self.running or self.game_over:
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        if (
            new_head[0] < 0
            or new_head[0] >= self.cols
            or new_head[1] < 0
            or new_head[1] >= self.rows
            or new_head in self.snake[:-1]
        ):
            self.running = False
            self.game_over = True
            self._update_labels("Game Over")
            self.board.invalidate()
            return

        self.snake.insert(0, new_head)
        if self.food is not None and new_head == self.food:
            self.score += 1
            self.spawn_food()
            self._update_labels("Good!")
        else:
            self.snake.pop()
            self._update_labels("Running")

        self.board.invalidate()

    def on_enter(self):
        dprint(DEBUG_INFO, "SnakeApp on_enter")
        self.screen.invalidate()
        self.set_timer(self.TIMER_STEP, self.step_ms, repeat=-1)

    def on_pause(self):
        dprint(DEBUG_INFO, "SnakeApp on_pause")

    def on_resume(self):
        dprint(DEBUG_INFO, "SnakeApp on_resume")
        self.screen.invalidate()

    def on_exit(self):
        dprint(DEBUG_INFO, "SnakeApp on_exit")
        self.cancel_timer(self.TIMER_STEP)
        self.cancel_timer(self.TIMER_EXIT)

    def on_timer(self, timer_id):
        if timer_id == self.TIMER_STEP:
            self._step()
        elif timer_id == self.TIMER_EXIT:
            exit_app()

    def on_input(self, key, status):
        if key in (GPIO_KEY_MENU, BLE_KEY_MENU):
            if status == KEY_S_PRESSED:
                self.set_timer(self.TIMER_EXIT, 1200)
            elif status == KEY_S_RELEASED:
                self.cancel_timer(self.TIMER_EXIT)
            return

        if status != KEY_S_PRESSED:
            return

        if key in (GPIO_KEY_ENTER, BLE_KEY_ENTER):
            if self.game_over:
                self.reset_game()
                self.running = True
            else:
                self.running = not self.running
            self._update_labels("Running" if self.running else "Paused")
            self.board.invalidate()
            return

        if key == BLE_KEY_UP:
            self._set_absolute_direction(self.DIR_UP)
        elif key == BLE_KEY_DOWN:
            self._set_absolute_direction(self.DIR_DOWN)
        elif key == BLE_KEY_LEFT:
            self._set_absolute_direction(self.DIR_LEFT)
        elif key == BLE_KEY_RIGHT:
            self._set_absolute_direction(self.DIR_RIGHT)
        elif key == GPIO_KEY_PREV:
            self._turn_left()
        elif key == GPIO_KEY_NEXT:
            self._turn_right()

    def render(self):
        self.screen.show()
