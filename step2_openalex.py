"""
Step 2: 논문 메타데이터 보강 (Semantic Scholar)
- 구 OpenAlex 버전에서 S2로 교체됨
- step2_s2.py 를 호출하는 wrapper

실행: python step2_openalex.py  (또는 python step2_s2.py 직접 실행)
"""
import subprocess
import sys

if __name__ == '__main__':
    print("step2_openalex.py → step2_s2.py 로 위임 (Semantic Scholar 사용)")
    subprocess.run([sys.executable, 'step2_s2.py'] + sys.argv[1:])
