#!/bin/bash

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn1 --gpu_no 0 --seed 1234 --lr 0.01

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn2 --gpu_no 0 --seed 1234 --lr 0.01

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn3 --gpu_no 0 --seed 1234 --lr 0.01

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn1-relu --gpu_no 0 --seed 1234 --lr 0.01

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn2-relu --gpu_no 0 --seed 1234 --lr 0.01

 python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model ekut-raw-cnn3-relu --gpu_no 0 --seed 1234 --lr 0.01



python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-ds-cnn-small --gpu_no 0 --window_ms 40 --stride_ms 20 --n_dct 10 --lr 0.01

python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-ds-cnn-medium --gpu_no 0 --window_ms 40 --stride_ms 20 --n_dct 10 --lr 0.01

python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-ds-cnn-large --gpu_no 0 --window_ms 40 --stride_ms 20 --n_dct 10  --lr 0.01




python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-dnn-small --gpu_no 0 --window_ms 40 --stride_ms 40 --n_dct 10 --lr 0.001

python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-dnn-medium --gpu_no 0 --window_ms 40 --stride_ms 40 --n_dct 10 --lr 0.001

python3.6 -m speech_recognition.train --data_folder datasets/speech_commands_v0.02/ --wanted_words yes no up down left right on off stop go --n_labels 12 --n_epochs 500 --model hello-dnn-large --gpu_no 0 --window_ms 40 --stride_ms 40 --n_dct 10  --lr 0.001


