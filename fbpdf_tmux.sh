#!/bin/sh

# check args

test $# -ge 1 || { echo "At least one argument needed"; exit 1; }
test -t 0 -a -t 1 -a -t 2 || { echo "must be run from a TTY" >&2; exit 1; }

python3 ./pdf_render.py "$@" 1>/dev/null &
PID1=$!
tmux new-session -d -s mumux
tmux bind NPage run-shell "echo -n n | nc -U /tmp/my_fbpdf_server"
tmux bind PPage run-shell "echo -n p | nc -U /tmp/my_fbpdf_server"
tmux bind Tab run-shell "echo -n N | nc -U /tmp/my_fbpdf_server"
W=$((`tput cols`/2))
H=`tput lines`
tmux attach-session -t mumux \; resize-window -x $W -y $H 
trap "kill $PID1" EXIT
