KEY_ANSWER = 'key.wav'
GAME_START = 'game_start.wav'
GAME_STOP = 'game_stop.wav'
SET_FINISH = 'set_finish.wav'
GAME_PINGPONG = 'pingpong.wav'

def number_to_voice_files(num):
    # 定义数字和单位对应的音频文件
    units = ['', 'shi.wav', 'bai.wav', 'qian.wav', 'wan.wav']
    digits = ['0.wav', '1.wav', '2.wav', '3.wav', '4.wav', '5.wav', '6.wav', '7.wav', '8.wav', '9.wav']
    
    # 特殊情况：0 的处理
    if num == 0:
        return [digits[0]]
    
    result = []
    unit_pos = 0
    prev_digit = None  # 用于记录前一个数字，避免处理重复的 "零"
    
    # 循环处理数字的每一位
    while num > 0:
        digit = num % 10
        num //= 10
        
        # 如果该位数字不是 0，插入数字音频文件
        if digit != 0:
            result.insert(0, digits[digit])
            # 如果该位不是最低位，且单位不是空，插入单位音频文件
            if unit_pos > 0:
                result.insert(1, units[unit_pos])  # 向第二个位置插入单位，防止单位和数字顺序错误
        elif prev_digit != 0:  # 只有前一位数字不为 0 时才插入 "零"
            result.insert(0, digits[0])  # "零" 的音频文件
        
        # 更新单位
        prev_digit = digit
        unit_pos += 1
    
    # 处理末尾的零：如果最后一个数字是零，则移除末尾的零
    if result[-1] == '0.wav':  # 如果末尾是“零”，就去掉它
        result.pop()
    
    # 开头以一十X略为十X
    if len(result) > 1 and result[0] == '1.wav' and result[1] == 'shi.wav':
        result = result[1:]

    return result

def build_score_files(score1, score2):
    score1_files = number_to_voice_files(score1)
    score2_files = number_to_voice_files(score2)

    score_files = score1_files + ['bi.wav'] + score2_files

    return score_files
