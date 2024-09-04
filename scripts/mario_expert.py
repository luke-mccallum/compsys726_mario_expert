"""
This the primary class for the Mario Expert agent. It contains the logic for the Mario Expert agent to play the game and choose actions.

Your goal is to implement the functions and methods required to enable choose_action to select the best action for the agent to take.

Original Mario Manual: https://www.thegameisafootarcade.com/wp-content/uploads/2017/04/Super-Mario-Land-Game-Manual.pdf
"""

import json
import logging
import math
import cv2

from enum import IntEnum
from mario_environment import MarioEnvironment
from pyboy.utils import WindowEvent

class Sprites(IntEnum):
    AIR = 0
    MARIO = 1
    BLOCK = 10
    MOVING_PLATFORM = 11
    BRICK = 12
    POWERUP_BLOCK = 13
    PIPE = 14
    GOOMBA = 15
    KOOPA = 16
    FLY = 18
    BEE = 19
    SHELL = 25

class Actions(IntEnum):
    LEFT = 1
    RIGHT = 2
    UP = 3
    JUMP = 4
    SPRINT = 5


class MarioController(MarioEnvironment):
    """
    The MarioController class represents a controller for the Mario game environment.

    You can build upon this class all you want to implement your Mario Expert agent.

    Args:
        act_freq (int): The frequency at which actions are performed. Defaults to 10.
        emulation_speed (int): The speed of the game emulation. Defaults to 0.
        headless (bool): Whether to run the game in headless mode. Defaults to False.
    """

    def __init__(
        self,
        act_freq: int = 1,
        emulation_speed: int = 1,
        headless: bool = False,
    ) -> None:
        super().__init__(
            act_freq=act_freq,
            emulation_speed=emulation_speed,
            headless=headless,
        )

        self.act_freq = act_freq

        # Example of valid actions based purely on the buttons you can press
        valid_actions: list[WindowEvent] = [
            WindowEvent.PRESS_ARROW_DOWN,
            WindowEvent.PRESS_ARROW_LEFT,
            WindowEvent.PRESS_ARROW_RIGHT,
            WindowEvent.PRESS_ARROW_UP,
            WindowEvent.PRESS_BUTTON_A,
            WindowEvent.PRESS_BUTTON_B,
        ]

        release_button: list[WindowEvent] = [
            WindowEvent.RELEASE_ARROW_DOWN,
            WindowEvent.RELEASE_ARROW_LEFT,
            WindowEvent.RELEASE_ARROW_RIGHT,
            WindowEvent.RELEASE_ARROW_UP,
            WindowEvent.RELEASE_BUTTON_A,
            WindowEvent.RELEASE_BUTTON_B,
        ]

        self.valid_actions = valid_actions
        self.release_button = release_button

    def run_action(self, action, duration) -> None:
        if action == Actions.JUMP:
            self.pyboy.send_input(self.valid_actions[Actions.RIGHT.value])
            self.pyboy.send_input(self.valid_actions[Actions.SPRINT.value])
            self.pyboy.send_input(self.valid_actions[Actions.JUMP.value])

            for _ in range(self.act_freq * duration):
                self.pyboy.tick()

            self.pyboy.send_input(self.release_button[Actions.JUMP.value])
            self.pyboy.send_input(self.release_button[Actions.SPRINT.value])
            self.pyboy.send_input(self.release_button[Actions.RIGHT.value])

        elif action == Actions.RIGHT:
            self.pyboy.send_input(self.valid_actions[Actions.RIGHT.value])
            self.pyboy.send_input(self.valid_actions[Actions.SPRINT.value])

            for _ in range(self.act_freq * duration):
                self.pyboy.tick()

            self.pyboy.send_input(self.release_button[Actions.SPRINT.value])
            self.pyboy.send_input(self.release_button[Actions.RIGHT.value])

        else:
            self.pyboy.send_input(self.valid_actions[action.value])

            for _ in range(self.act_freq * duration):
                self.pyboy.tick()

            self.pyboy.send_input(self.release_button[action.value])


class MarioExpert:
    """
    The MarioExpert class represents an expert agent for playing the Mario game.

    Edit this class to implement the logic for the Mario Expert agent to play the game.

    Do NOT edit the input parameters for the __init__ method.

    Args:
        results_path (str): The path to save the results and video of the gameplay.
        headless (bool, optional): Whether to run the game in headless mode. Defaults to False.
    """

    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path
        self.environment = MarioController(headless=headless)
        self.video = None 
        self.prev_action = None
        self.mario_pos = None
        self.game_area = None

    # Get coordinates of bottom right corner of Mario sprite
    def get_mario_pos(self):
        rows, cols = self.game_area.shape
        for x in range(rows): 
            for y in range(cols):
                if self.game_area[x][y] == Sprites.MARIO.value:
                    return (x + 1, y + 1)
        return 0, 0
    
    # Check if there is air beneath Mario
    def get_is_airborne(self):
        if self.game_area[self.mario_pos[0] + 1][self.mario_pos[1]] == Sprites.AIR.value: 
            return True;
        return False;
    
    # Determine the position and identity of the nearest enemy in front of Mario
    def get_enemy_info(self):
        cols = self.game_area.shape[1]
        mx, my = self.mario_pos
        for xoffset in range(mx): 
            x = mx - xoffset
            for yoffset in range(cols - my):
                y = my + yoffset
                if self.game_area[x][y] >= Sprites.GOOMBA.value:
                    return (mx - x, yoffset, self.game_area[x][y])
        return (100, 100, 100)
    
    # Determine the position of obstacles blocking Mario
    def get_obstacle_info(self):
        mx, my = self.mario_pos
        for y in range(6):
            val = self.game_area[mx][my + y];
            if val == Sprites.BRICK.value or val == Sprites.PIPE.value or val == Sprites.BLOCK.value:
                x = mx
                while self.game_area[x][my + y] != Sprites.AIR.value:
                    x -= 1
                return y, mx - x + 1
        return 100, 100
    
    # Check if there is a platform above Mario
    def get_platform_above(self):
        mx, my = self.mario_pos
        for y in range (6):
            y += 1
            for x in range(mx - 1):
                if ((self.game_area[x][my + y] == Sprites.BRICK.value or 
                     self.game_area[x][my + y] == Sprites.BLOCK.value) and
                     self.game_area[x - 1][my + y] == Sprites.AIR.value and
                     self.game_area[x][my + y - 1] == Sprites.AIR.value):
                    return mx - x, y
        return 100, 100
    
    # Determine the size and positions of pits in front of Mario
    def get_pit_info(self):
        rows, cols = self.game_area.shape
        mx, my = self.mario_pos
        for yoffset in range(cols - my):
            y = my + yoffset
            if self.game_area[mx + 1][y] == Sprites.AIR.value and self.game_area[15][y] == Sprites.AIR.value:
                for a in range(rows):
                    for boffset in range(cols - y):
                        b = y + boffset
                        if self.game_area[a][b] >= Sprites.BLOCK.value and self.game_area[a][b] <= Sprites.PIPE.value:
                            return yoffset, mx - a, b - my
        return 100, 100, 100
    
    # Get the distance to a point using the pythagorean theorem
    def get_pythag_dist(self, a, b): return math.ceil(math.sqrt(a**2 + b**2))

    # Choosing Action
    def choose_action(self):
        self.game_area = self.environment.game_area()
        self.mario_pos = self.get_mario_pos()

        # Break if Mario is out of bounds (Dead or Level Complete)
        if (self.mario_pos[0] >= 15 or self.mario_pos[1] >= 15):
            return Actions.RIGHT, 1
        
        enemy_info = self.get_enemy_info()
        pit_info = self.get_pit_info()
        obstacle_info = self.get_obstacle_info()
        is_airborne = self.get_is_airborne()
        platform = self.get_platform_above()

        action = Actions.RIGHT
        duration = 1

        # Jump over upcoming obstacles
        if obstacle_info[0] < 3 and is_airborne == False:
            print("Jump over obstacle of height ", obstacle_info[1])
            action = Actions.JUMP
            duration = obstacle_info[1] * 2

        # Jump onto upcoming platforms
        elif platform[1] < 6 and platform[0] < 6 and platform[0] != obstacle_info[0]: 
            print("Jump onto platform at ", platform)
            action = Actions.JUMP
            duration = platform[0] * 3
            if (pit_info[0] < platform[1]): 
                duration += 10
        
        # Check if Goomba or Koopa are right in front of Mario
        elif enemy_info[2] < 18 and enemy_info[1] < 2:
            print("Goomba/Koopa ahead")
            # Prevent collision with enemy
            if self.prev_action == Actions.JUMP:
                action = Actions.LEFT
                duration = 1
            # Jump over/onto enemy
            else: 
                action = Actions.JUMP
                duration = 1

        # Jump over Flies
        elif enemy_info[2] == 19 and enemy_info[1] < 4:
            print("Fly ahead")
            action = Actions.JUMP
            duration = enemy_info[0] + 10

        # Jump over upcoming pits
        elif pit_info[0] < 2 and is_airborne == False:
            print("Pit is", pit_info[0], "away and other side at", pit_info[1], pit_info[2])
            action = Actions.JUMP
            duration = self.get_pythag_dist(max(4, pit_info[1]), pit_info[2])

        # Prevent Mario from getting stuck
        if self.prev_action == action and action == Actions.JUMP:
            print('Prevented jump loop')
            action = Actions.RIGHT
            duration = 1
        self.prev_action = action

        return action, duration

    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """

        # Choose an action - button press or other...
        action, duration = self.choose_action()

        # Run the action on the environment
        self.environment.run_action(action, duration)

    def play(self):
        """
        Do NOT edit this method.
        """
        self.environment.reset()

        frame = self.environment.grab_frame()
        height, width, _ = frame.shape

        self.start_video(f"{self.results_path}/mario_expert.mp4", width, height)

        while not self.environment.get_game_over():
            frame = self.environment.grab_frame()
            self.video.write(frame)

            self.step()

        final_stats = self.environment.game_state()
        logging.info(f"Final Stats: {final_stats}")

        with open(f"{self.results_path}/results.json", "w", encoding="utf-8") as file:
            json.dump(final_stats, file)

        self.stop_video()

    def start_video(self, video_name, width, height, fps=30):
        """
        Do NOT edit this method.
        """
        self.video = cv2.VideoWriter(
            video_name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    def stop_video(self) -> None:
        """
        Do NOT edit this method.
        """
        self.video.release()
