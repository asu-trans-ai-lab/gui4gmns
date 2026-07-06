#!/usr/bin/env bash
# -static: bundle libgcc/libstdc++/libgomp (avoids the Git-mingw64 DLL mismatch; see TAPLite -O2 fix)
set -e
g++ -std=c++17 -O2 -Wall -fopenmp -static tests/test_main.cpp -o dlsim_test.exe
g++ -std=c++17 -O2 -Wall -fopenmp -static tools/dlsim_run.cpp -o dlsim_run.exe
echo "built dlsim_test.exe + dlsim_run.exe (OpenMP)"
