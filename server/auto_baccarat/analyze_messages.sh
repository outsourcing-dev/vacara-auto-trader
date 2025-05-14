#!/bin/bash

# 모든 메시지 타입을 로깅하고 테이블 정보를 분석하는 스크립트

echo "======================================================"
echo "     바카라 로비 WebSocket 메시지 분석 도구     "
echo "======================================================"
echo "이 스크립트는 WebSocket 연결에서 오는 모든 메시지 타입을"
echo "분석하여 테이블 이름 정보를 찾는데 도움을 줍니다."
echo ""
echo "디버그 모드로 실행하고 로그를 message_types.log 파일에 저장합니다."
echo "======================================================"
echo ""

# 디버그 모드로 실행
python main.py --debug --filter-off | tee message_types.log

# 결과 분석
echo ""
echo "======================================================"
echo "메시지 타입 분석 결과"
echo "======================================================"
echo "발견된 메시지 타입:"
grep "메시지 타입:" message_types.log | sort | uniq -c | sort -rn

echo ""
echo "테이블 관련 메시지:"
grep -i "table\|lobby" message_types.log | grep -v "lobby.historyUpdated" | head -20

echo ""
echo "로그 파일 message_types.log에서 더 자세한 내용을 확인하세요."
echo "======================================================"