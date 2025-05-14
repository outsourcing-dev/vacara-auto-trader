#!/bin/bash

# 방 정보를 찾기 위한 연결 요청 분석 스크립트

echo "======================================================"
echo "     바카라 로비 초기 연결 메시지 분석 도구     "
echo "======================================================"
echo "이 스크립트는 프로그램 시작 시 WebSocket 초기 메시지를"
echo "분석하여 방 이름 정보를 찾는데 도움을 줍니다."
echo ""
echo "실행이 완료되면 Ctrl+C를 눌러 종료하세요."
echo "======================================================"
echo ""

# 디버그 모드로 실행하고 최초 30초 동안의 로그만 캡처
timeout 30s python main.py --debug --filter-off | tee initial_connection.log

# 분석 결과 정리
echo ""
echo "======================================================"
echo "초기 연결 메시지 분석"
echo "======================================================"
echo "1. 테이블 관련 메시지 확인:"
grep -i "tables\|tableInfo\|lobby.\|table_" initial_connection.log | head -20

echo ""
echo "2. lobby. 타입의 메시지:"
grep "메시지 타입: lobby." initial_connection.log | sort | uniq

echo ""
echo "3. 연결 직후 받은 첫 5개 메시지:"
cat initial_connection.log | grep "메시지 내용" | head -5

echo ""
echo "로그 파일 initial_connection.log에서 더 자세한 내용을 확인하세요."
echo "======================================================"