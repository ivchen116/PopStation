
class GameRule:
    def is_game_won(self, p1_score, p2_score):
        raise NotImplementedError

    def next_server(self, current_server, scorer, p1_score, p2_score):
        raise NotImplementedError

class Scoreboard:
    def __init__(self, rule, player1="Player1", player2="Player2"):
        self.rule = rule

        self.player1_name = player1
        self.player2_name = player2

        self.player1_score = 0
        self.player2_score = 0
        self.games_player1 = 0
        self.games_player2 = 0
        self.current_game = 1
        self.server = 1
        self.game_ended = False

    def change_rule(self, rule):
        if rule == self.rule:
            return
        self.reset_game()
        self.rule = rule

    def reset_game(self):
        """重置当前局分数（不改变局分），并清除结束标志"""
        self.player1_score = 0
        self.player2_score = 0
        self.game_ended = False

    def start_new_game(self):
        """开始新的一局（同 reset_game，用于外部调用）"""
        if self.game_ended:
            if self.player1_score > self.player2_score:
                self.games_player1 += 1
            else:
                self.games_player2 += 1 
            self.current_game += 1
        self.reset_game()

    def score_point(self, player):
        if self.game_ended:
            return False, self.player1_score, self.player2_score

        if player == 1:
            self.player1_score += 1
        elif player == 2:
            self.player2_score += 1
        else:
            raise ValueError("玩家必须是1或2")

        self.server = self.rule.next_server(
                self.server,
                player,
                self.player1_score,
                self.player2_score
            )

        if self.rule.is_game_won(self.player1_score, self.player2_score):
            self.end_game()
            return True, self.player1_score, self.player2_score

        return False, self.player1_score, self.player2_score

    def end_game(self):
        self.game_ended = True

    def reset_game(self):
        self.player1_score = 0
        self.player2_score = 0
        self.game_ended = False

    def get_end_status(self):
        return self.game_ended

    def get_server(self):
        return self.server

    def get_score(self):
        return self.player1_score, self.player2_score

    def get_game_status(self):
        return self.current_game, self.games_player1, self.games_player2

    def start_new_match(self):
        """开始新比赛：重置所有数据"""
        self.current_game = 1
        self.games_player1 = 0
        self.games_player2 = 0
        self.reset_game()               # 重置分数并清除结束标志


class TableTennisRule(GameRule):
    def __init__(self):
        self.win_score = 11
        self.win_margin = 2

    def is_game_won(self, p1, p2):
        return (
            (p1 >= self.win_score and p1 - p2 >= self.win_margin) or
            (p2 >= self.win_score and p2 - p1 >= self.win_margin)
        )

    def next_server(self, current_server, scorer, p1, p2):
        total_points = p1 + p2

        # 10:10之后，每分交换
        if p1 >= 10 and p2 >= 10:
            return 2 if current_server == 1 else 1

        # 正常情况：每2分换发球
        if total_points % 2 == 0:
            return 2 if current_server == 1 else 1

        return current_server


class BadmintonRule(GameRule):
    def __init__(self):
        self.win_score = 21
        self.win_margin = 2
        self.max_score = 30

    def is_game_won(self, p1, p2):
        if p1 == self.max_score or p2 == self.max_score:
            return True

        return (
            (p1 >= self.win_score and p1 - p2 >= self.win_margin) or
            (p2 >= self.win_score and p2 - p1 >= self.win_margin)
        )

    def next_server(self, current_server, scorer, p1, p2):
        # 谁得分谁发球
        return scorer

# # 乒乓球
# tt = Scoreboard(TableTennisRule())

# tt.score_point(1)
# print("比分:", tt.get_score(), "发球:", tt.get_server())

# # 羽毛球
# bm = Scoreboard(BadmintonRule())

# bm.score_point(2)
# print("比分:", bm.get_score(), "发球:", bm.get_server())