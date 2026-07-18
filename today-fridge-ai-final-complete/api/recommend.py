import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


MAX_BODY_BYTES = 20_000
MAX_INGREDIENTS = 30
MODEL = "gemini-3.5-flash"


def send_json(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def extract_json(text):
    text = (text or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI 응답에서 JSON을 찾지 못했습니다.")

    return json.loads(text[start:end + 1])


def validate_payload(payload):
    ingredients = payload.get("ingredients")
    condition = payload.get("condition", "")

    if not isinstance(ingredients, list):
        raise ValueError("재료 목록 형식이 올바르지 않습니다.")

    cleaned = []
    seen = set()

    for item in ingredients:
        if not isinstance(item, str):
            continue
        value = " ".join(item.strip().split())
        key = value.lower()

        if value and key not in seen:
            cleaned.append(value)
            seen.add(key)

    if not cleaned:
        raise ValueError("재료를 하나 이상 입력해 주세요.")

    if len(cleaned) > MAX_INGREDIENTS:
        raise ValueError("재료는 최대 30개까지 입력할 수 있습니다.")

    if not isinstance(condition, str):
        condition = ""

    return cleaned, condition.strip()[:300]


def build_prompt(ingredients, condition):
    condition_text = condition or "특별한 조건 없음"

    return f'''
당신은 한국 가정식을 잘 아는 친절한 냉장고 파먹기 요리 전문가입니다.

사용자가 보유한 재료:
{", ".join(ingredients)}

원하는 조건:
{condition_text}

위 정보를 바탕으로 서로 겹치지 않는 현실적인 레시피를 정확히 5개 추천하세요.

중요 규칙:
1. 한국어로 작성합니다.
2. 사용자가 가진 재료를 최대한 우선 사용합니다.
3. 소금, 설탕, 식용유, 간장, 후추 같은 기본 양념은 있다고 가정할 수 있습니다.
4. 없는 핵심 재료가 필요하면 ingredients 항목에 "(추가 필요)"라고 표시합니다.
5. 위험한 조리법이나 식품 안전상 부적절한 내용은 쓰지 않습니다.
6. 아래 JSON 형식 외의 문장, 설명, 코드 블록을 절대 출력하지 않습니다.
7. recipes 배열에는 반드시 정확히 5개 객체가 있어야 합니다.
8. 각 steps 배열은 3~6개의 짧고 구체적인 단계로 작성합니다.

반환 JSON 형식:
{{
  "recipes": [
    {{
      "id": "recipe-1",
      "name": "요리 이름",
      "summary": "이 요리를 추천하는 이유를 한두 문장으로 설명",
      "time": "약 20분",
      "difficulty": "쉬움",
      "ingredients": ["재료와 대략적인 양"],
      "steps": ["1단계 내용", "2단계 내용", "3단계 내용"],
      "tip": "재료 절약 또는 대체 팁"
    }}
  ]
}}
'''.strip()


def call_gemini(api_key, prompt):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={api_key}"
    )

    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API 오류({error.code}): {detail[:300]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError("Gemini API에 연결하지 못했습니다.") from error

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini API 응답에 추천 내용이 없습니다.") from error


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        send_json(self, 200, {
            "success": True,
            "message": "냉털 AI API가 정상 작동 중입니다."
        })

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))

            if content_length <= 0 or content_length > MAX_BODY_BYTES:
                raise ValueError("요청 데이터의 크기가 올바르지 않습니다.")

            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            ingredients, condition = validate_payload(payload)

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                send_json(self, 500, {
                    "success": False,
                    "error": {
                        "message": "Vercel 환경 변수 GEMINI_API_KEY가 등록되지 않았습니다."
                    }
                })
                return

            prompt = build_prompt(ingredients, condition)
            ai_text = call_gemini(api_key, prompt)
            parsed = extract_json(ai_text)
            recipes = parsed.get("recipes")

            if not isinstance(recipes, list) or len(recipes) != 5:
                raise ValueError("AI가 레시피 5개를 올바르게 반환하지 않았습니다.")

            send_json(self, 200, {
                "success": True,
                "recipes": recipes
            })

        except json.JSONDecodeError:
            send_json(self, 400, {
                "success": False,
                "error": {"message": "요청 JSON 형식이 올바르지 않습니다."}
            })
        except ValueError as error:
            send_json(self, 400, {
                "success": False,
                "error": {"message": str(error)}
            })
        except Exception as error:
            print(f"recommend error: {error}")
            send_json(self, 500, {
                "success": False,
                "error": {
                        "message": "추천을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        }
    })
