export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({
      success: false,
      message: "POST 요청만 가능합니다.",
    });
  }

  try {
    const { ingredients, conditions } = req.body || {};

    if (!Array.isArray(ingredients) || ingredients.length === 0) {
      return res.status(400).json({
        success: false,
        message: "냉장고 재료를 한 개 이상 입력해 주세요.",
      });
    }

    const apiKey = process.env.GEMINI_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        success: false,
        message: "GEMINI_API_KEY가 설정되지 않았습니다.",
      });
    }

    const prompt = `
당신은 냉장고 재료를 활용해 현실적으로 만들 수 있는 요리를 추천하는 요리 전문가입니다.

사용 가능한 재료:
${ingredients.join(", ")}

추가 조건:
${conditions || "특별한 조건 없음"}

반드시 서로 다른 레시피 5개를 한국어로 추천하세요.

각 레시피는 다음 형식으로 작성하세요.

1. 요리 이름
- 사용 재료:
- 예상 조리 시간:
- 난이도:
- 만드는 방법:
  1)
  2)
  3)
- 부족한 재료가 있다면:

입력하지 않은 재료는 최소한으로 사용하고, 일반적인 양념은 사용할 수 있습니다.
`;

    const response = await fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": apiKey,
        },
        body: JSON.stringify({
          contents: [
            {
              role: "user",
              parts: [{ text: prompt }],
            },
          ],
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      console.error(data);

      return res.status(response.status).json({
        success: false,
        message:
          data?.error?.message || "Gemini API 요청 중 오류가 발생했습니다.",
      });
    }

    const text =
      data?.candidates?.[0]?.content?.parts
        ?.map((part) => part.text || "")
        .join("") || "";

    if (!text) {
      return res.status(500).json({
        success: false,
        message: "AI가 레시피를 생성하지 못했습니다.",
      });
    }

    return res.status(200).json({
      success: true,
      result: text,
    });
  } catch (error) {
    console.error(error);

    return res.status(500).json({
      success: false,
      message: "서버 오류가 발생했습니다.",
    });
  }
}