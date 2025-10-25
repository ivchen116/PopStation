@echo off
if not exist trimmed mkdir trimmed
for %%f in (*.wav) do (
  echo Processing %%f ...
  ffmpeg -y -i "%%f" -af "silenceremove=stop_periods=-1:start_threshold=-40dB:start_silence=0.05:stop_threshold=-40dB:stop_silence=0.15" "trimmed/%%~nf.wav"
)
pause
