import arcade
import math
import random
import time

from arcade.particles import FadeParticle, Emitter, EmitMaintainCount
from pyglet.graphics import Batch

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = "ricev1"
TILE_SCALING = 0.5

CAMERA_LERP = 0.12

PLAYER_MAX_SPEED = 10
PLAYER_MIN_SPEED = 2
PLAYER_BUST = 0.3
PLAYER_DECELERATION = 0.2
PLAYER_ROTATION_SPEED = 5

SLOW_ROAD_FACTOR = 0.4

SPARK_TEX = [
    arcade.make_soft_circle_texture(8, arcade.color.GRAY),
    arcade.make_soft_circle_texture(8, arcade.color.DARK_GRAY),
    arcade.make_soft_circle_texture(8, arcade.color.WHITE_SMOKE),
    arcade.make_soft_circle_texture(8, arcade.color.BLACK),
]


def make_wheel_trail(attached_sprite, wheel_offset_x, wheel_offset_y, maintain=30):
    angle_rad = math.radians(attached_sprite.angle)
    rotated_x = wheel_offset_x * math.cos(angle_rad) - wheel_offset_y * math.sin(angle_rad)
    rotated_y = wheel_offset_x * math.sin(angle_rad) + wheel_offset_y * math.cos(angle_rad)

    emit = Emitter(
        center_xy=(attached_sprite.center_x + rotated_x,
                   attached_sprite.center_y + rotated_y),
        emit_controller=EmitMaintainCount(maintain),
        particle_factory=lambda e: FadeParticle(
            filename_or_texture=random.choice(SPARK_TEX),
            change_xy=arcade.math.rand_in_circle((0.0, 0.0), 1.2),
            lifetime=random.uniform(0.3, 0.5),
            start_alpha=180, end_alpha=0,
            scale=random.uniform(0.6, 0.6),
        ),
    )
    emit._attached = attached_sprite
    emit._wheel_offset_x = wheel_offset_x
    emit._wheel_offset_y = wheel_offset_y
    return emit


class MenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.background_color = arcade.color.BLUE_GRAY

        self.batch = Batch()
        self.main_text = arcade.Text("Главное Меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 100,
                                     arcade.color.WHITE, font_size=40, anchor_x="center", batch=self.batch)

        self.easy_text = arcade.Text("1 - Лёгкий режим", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2,
                                     arcade.color.WHITE, font_size=24, anchor_x="center", batch=self.batch)

        self.hard_text = arcade.Text("2 - Сложный режим", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50,
                                     arcade.color.WHITE, font_size=24, anchor_x="center", batch=self.batch)

        self.space_text = arcade.Text("Нажми 1 или 2 для выбора", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 150,
                                      arcade.color.YELLOW, font_size=20, anchor_x="center", batch=self.batch)

    def on_draw(self):
        self.clear()
        self.batch.draw()

    def on_key_press(self, key, modifiers):
        if key == arcade.key.KEY_1 or key == arcade.key.NUM_1:
            game_view = GameView("easy")
            self.window.show_view(game_view)
        elif key == arcade.key.KEY_2 or key == arcade.key.NUM_2:
            game_view = GameView("hard")
            self.window.show_view(game_view)


class ResultsView(arcade.View):

    def __init__(self, race_time, difficulty):
        super().__init__()
        self.race_time = race_time
        self.difficulty = difficulty
        self.background_color = arcade.color.DARK_BLUE

        self.batch = Batch()

        minutes = int(race_time // 60)
        seconds = int(race_time % 60)
        milliseconds = int((race_time % 1) * 1000)
        time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

        self.title_text = arcade.Text("ГОНКА ЗАВЕРШЕНА!", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                                      arcade.color.GOLD, font_size=36, anchor_x="center", batch=self.batch)

        self.time_text = arcade.Text(f"Ваше время: {time_str}", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50,
                                     arcade.color.WHITE, font_size=28, anchor_x="center", batch=self.batch)

        self.difficulty_text = arcade.Text(f"Режим: {'Лёгкий' if difficulty == 'easy' else 'Сложный'}",
                                           SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2,
                                           arcade.color.WHITE, font_size=24, anchor_x="center", batch=self.batch)

        self.instruction_text = arcade.Text("Нажми SPACE для новой гонки", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 100,
                                            arcade.color.YELLOW, font_size=20, anchor_x="center", batch=self.batch)

        self.esc_text = arcade.Text("ESC для выхода в меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 150,
                                    arcade.color.YELLOW, font_size=20, anchor_x="center", batch=self.batch)

    def on_draw(self):
        self.clear()
        self.batch.draw()

    def on_key_press(self, key, modifiers):
        if key == arcade.key.SPACE:
            game_view = GameView(self.difficulty)
            self.window.show_view(game_view)
        elif key == arcade.key.ESCAPE:
            menu_view = MenuView()
            self.window.show_view(menu_view)


class GameView(arcade.View):
    def __init__(self, difficulty="easy"):
        super().__init__()
        self.difficulty = difficulty
        self.background_music = arcade.load_sound("DRIVE.wav")
        self.current_speed = 0
        self.target_speed = 0
        self.on_slow_road = False
        self.finished = False
        self.race_start_time = None
        self.race_time = 0

        self.wheel_emitters = []
        self.is_moving = False

        self.world_camera = arcade.camera.Camera2D()
        self.gui_camera = arcade.camera.Camera2D()

        self.tile_map = None
        self.slow_road_list = None
        self.finish_list = None

        self.player_list = arcade.SpriteList()

        self.player = None

        self.move_forward = False
        self.move_backward = False
        self.turn_left = False
        self.turn_right = False

        self.world_width = SCREEN_WIDTH
        self.world_height = SCREEN_HEIGHT

        self.batch = Batch()
        self.speed_text = arcade.Text("", 20, SCREEN_HEIGHT - 40, arcade.color.WHITE, 20, batch=self.batch)
        self.time_text = arcade.Text("", 20, SCREEN_HEIGHT - 70, arcade.color.WHITE, 20, batch=self.batch)
        self.info_text = arcade.Text(
            f"Режим: {'Лёгкий' if difficulty == 'easy' else 'Сложный'} | "
            "WASD - движение | ESC - меню",
            20, 20, arcade.color.BLACK, 14, batch=self.batch
        )

        self.wheel_offsets = [
            (25, -15),
            (-25, -15)
        ]

        if difficulty == "easy":
            self.map_file = "racefirst.tmx"
            self.max_speed = PLAYER_MAX_SPEED * 0.8
            self.burst = PLAYER_BUST * 0.7
        else:
            self.map_file = "racesec.tmx"
            self.max_speed = PLAYER_MAX_SPEED * 0.8
            self.burst = PLAYER_BUST * 0.7

        self.setup()

    def setup(self):
        self.tile_map = arcade.load_tilemap(self.map_file, scaling=TILE_SCALING)
        self.wall_list = self.tile_map.sprite_lists["walls"]
        self.road_list = self.tile_map.sprite_lists["road"]
        self.spawn_list = self.tile_map.sprite_lists["spawn"]
        self.collision_list = self.tile_map.sprite_lists["collisions"]

        self.slow_road_list = self.tile_map.sprite_lists.get("slowroad", arcade.SpriteList())
        self.finish_list = self.tile_map.sprite_lists.get("finish", arcade.SpriteList())

        self.world_width = int(self.tile_map.width * self.tile_map.tile_width * TILE_SCALING)
        self.world_height = int(self.tile_map.height * self.tile_map.tile_height * TILE_SCALING)

        self.player_list = arcade.SpriteList()
        self.player = arcade.Sprite("PNG/caranime/car_blue_5.png", scale=0.5)

        if self.spawn_list and len(self.spawn_list) > 0:
            spawn_sprite = self.spawn_list[0]
            self.player.center_x = spawn_sprite.center_x
            self.player.center_y = spawn_sprite.center_y
            if hasattr(spawn_sprite, 'angle'):
                self.player.angle = spawn_sprite.angle

        self.player_list.append(self.player)

        self.physics_engine = arcade.PhysicsEngineSimple(
            self.player, self.collision_list
        )

        self.current_speed = 0
        self.finished = False
        self.race_start_time = time.time()
        self.race_time = 0
        if self.background_music:
            arcade.play_sound(self.background_music, volume=0.5, loop=True)

    def start_wheel_effects(self):
        if not self.is_moving and len(self.wheel_emitters) == 0:
            self.is_moving = True
            for offset_x, offset_y in self.wheel_offsets:
                emitter = make_wheel_trail(self.player, offset_x, offset_y, maintain=20)
                self.wheel_emitters.append(emitter)

    def on_key_press(self, key, modifiers):
        if self.finished:
            return

        if key == arcade.key.UP or key == arcade.key.W:
            self.move_forward = True
            self.start_wheel_effects()
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.move_backward = True
            self.start_wheel_effects()
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.turn_left = True
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.turn_right = True
        elif key == arcade.key.ESCAPE:
            menu_view = MenuView()
            self.window.show_view(menu_view)

    def on_key_release(self, key, modifiers):
        if key == arcade.key.UP or key == arcade.key.W:
            self.move_forward = False
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.move_backward = False
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.turn_left = False
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.turn_right = False

    def check_zones(self):
        if self.finished:
            return

        self.on_slow_road = False
        if self.slow_road_list:
            slow_collisions = arcade.check_for_collision_with_list(self.player, self.slow_road_list)
            self.on_slow_road = len(slow_collisions) > 0

        if self.finish_list and not self.finished:
            finish_collisions = arcade.check_for_collision_with_list(self.player, self.finish_list)
            if len(finish_collisions) > 0:
                self.finished = True
                self.race_time = time.time() - self.race_start_time

                results_view = ResultsView(self.race_time, self.difficulty)
                self.window.show_view(results_view)

    def update_speed(self, dt):
        if self.finished:
            return

        if self.move_forward:
            self.target_speed = self.max_speed
        elif self.move_backward:
            self.target_speed = -self.max_speed * 0.5
        else:
            self.target_speed = 0

        effective_max_speed = self.max_speed
        if self.on_slow_road:
            effective_max_speed = self.max_speed * SLOW_ROAD_FACTOR
            if self.target_speed > effective_max_speed:
                self.target_speed = effective_max_speed

        if abs(self.target_speed - self.current_speed) < 0.1:
            self.current_speed = self.target_speed
        elif self.target_speed > self.current_speed:
            self.current_speed += self.burst * dt * 60
            if self.current_speed > self.target_speed:
                self.current_speed = self.target_speed
        elif self.target_speed < self.current_speed:
            self.current_speed -= PLAYER_DECELERATION * dt * 60
            if self.current_speed < self.target_speed:
                self.current_speed = self.target_speed

        if abs(self.current_speed) < PLAYER_MIN_SPEED and self.target_speed != 0:
            self.current_speed = PLAYER_MIN_SPEED * (1 if self.target_speed > 0 else -1)

    def on_update(self, dt: float):
        if self.finished:
            return

        if self.race_start_time:
            self.race_time = time.time() - self.race_start_time

        minutes = int(self.race_time // 60)
        seconds = int(self.race_time % 60)
        milliseconds = int((self.race_time % 1) * 1000)
        time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        self.time_text.text = f"Время: {time_str}"
        self.speed_text.text = f"Скорость: {abs(self.current_speed):.1f} км/ч"

        self.update_speed(dt)

        self.check_zones()

        if self.turn_left:
            self.player.change_angle = -PLAYER_ROTATION_SPEED
        elif self.turn_right:
            self.player.change_angle = PLAYER_ROTATION_SPEED
        else:
            self.player.change_angle = 0

        if abs(self.current_speed) > 0.1:
            angle_rad = math.radians(self.player.angle)

            if self.current_speed > 0:
                self.player.change_x = math.sin(angle_rad) * self.current_speed
                self.player.change_y = math.cos(angle_rad) * self.current_speed
            else:
                self.player.change_x = math.sin(angle_rad) * self.current_speed
                self.player.change_y = math.cos(angle_rad) * self.current_speed
        else:
            self.player.change_x = 0
            self.player.change_y = 0

        for emitter in self.wheel_emitters:
            if hasattr(emitter, '_attached') and emitter._attached == self.player:
                angle_rad = math.radians(self.player.angle)
                offset_x = emitter._wheel_offset_x
                offset_y = emitter._wheel_offset_y

                rotated_x = offset_x * math.cos(angle_rad) - offset_y * math.sin(angle_rad)
                rotated_y = offset_x * math.sin(angle_rad) + offset_y * math.cos(angle_rad)

                emitter.center_x = self.player.center_x + rotated_x
                emitter.center_y = self.player.center_y + rotated_y

                emitter.update(dt)

        self.physics_engine.update()

        position = (
            self.player.center_x,
            self.player.center_y
        )
        self.world_camera.position = arcade.math.lerp_2d(
            self.world_camera.position,
            position,
            CAMERA_LERP
        )

    def on_draw(self):
        self.clear()

        self.world_camera.use()
        self.wall_list.draw()
        self.road_list.draw()

        if self.slow_road_list:
            self.slow_road_list.draw()
        if self.finish_list:
            self.finish_list.draw()

        self.player_list.draw()

        for emitter in self.wheel_emitters:
            emitter.draw()

        self.gui_camera.use()

        self.batch.draw()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, antialiasing=True)
    arcade.set_background_color(arcade.color.SKY_BLUE)

    menu_view = MenuView()
    window.show_view(menu_view)

    arcade.run()


if __name__ == "__main__":
    main()
