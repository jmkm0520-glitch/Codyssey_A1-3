export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({
      success: false,
      error: { message: "POST 요청만 가능합니다." }
    });
  }

  try {
    const { ingredients, condition } = req.body || {};

    if (!Array.isArray(ingredients) || ingredients.length === 0) {
      return res.status(400).json({
        success: false,
        error: { message: "냉장고 재료를 한 개 이상 입력해 주세요." }
      });
    }

    const apiKey = process.env.GEMINI_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        success: false,
        error: { message: "GEMINI_API_KEY가 설정되지 않았습니다." }
      });
    }

    const prompt = `
냉장고 재료를 활용해 실제로 만들 수 있는 서로 다른 한국어 레시피 5개를 추천하세요.

사용 가능한 재료:
${ingredients.join(", ")}

추가 조건:
${condition || "특별한 조건 없음"}

일반적인 양념은 사용할 수 있지만, 입력하지 않은 주요 재료 사용은 최소화하세요.
각 레시피에는 이름, 한 줄 설명, 조리 시간, 난이도, 재료 목록, 조리 순서, 냉털 팁을 포함하세요.
`;

    const geminiResponse = await fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": apiKey
        },
        body: JSON.stringify({
          contents: [
            {
              role: "user",
              parts: [{ text: prompt }]
            }
          ],
          generationConfig: {
            responseMimeType: "application/json",
            responseSchema: {
              type: "OBJECT",
              properties: {
                recipes: {
                  type: "ARRAY",
                  minItems: 5,
                  maxItems: 5,
                  items: {
                    type: "OBJECT",
                    properties: {
                      id: { type: "STRING" },
                      name: { type: "STRING" },
                      summary: { type: "STRING" },
                      time: { type: "STRING" },
                      difficulty: { type: "STRING" },
                      ingredients: {
                        type: "ARRAY",
                        items: { type: "STRING" }
                      },
                      steps: {
                        type: "ARRAY",
                        items: { type: "STRING" }
                      },
                      tip: { type: "STRING" }
                    },
                    required: [
                      "id",
                      "name",
                      "summary",
                      "time",
                      "difficulty",
                      "ingredients",
                      "steps",
                      "tip"
                    ]
                  }
                }
              },
              required: ["recipes"]
            }
          }
        })
      }
    );

    const data = await geminiResponse.json();

    if (!geminiResponse.ok) {
      return res.status(geminiResponse.status).json({
        success: false,
        error: {
          message:
            data?.error?.message || "Gemini API 요청에 실패했습니다."
        }
      });
    }

    const generatedText =
      data?.candidates?.[0]?.content?.parts
        ?.map((part) => part.text || "")
        .join("") || "";

    if (!generatedText) {
      return res.status(500).json({
        success: false,
        error: { message: "AI 추천 결과가 비어 있습니다." }
      });
    }

    const parsed = JSON.parse(generatedText);

    if (!Array.isArray(parsed.recipes) || parsed.recipes.length === 0) {
      return res.status(500).json({
        success: false,
        error: { message: "레시피 형식이 올바르지 않습니다." }
      });
    }

    return res.status(200).json({
      success: true,
      recipes: parsed.recipes
    });
  } catch (error) {
    console.error(error);

    return res.status(500).json({
      success: false,
      error: {
        message: "서버 오류가 발생했습니다."
      }
    });
  }
}