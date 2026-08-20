import json
import asyncio
from pathlib import Path
from typing import Optional, Callable
from config import GEMINI_API_KEY, AI_MODEL
from services.file_service import FileService
from services.terminal_service import TerminalService
from utils.logger import logger

SYSTEM_PROMPT = """
Sen Telegram Dev Bridge shaxsiy dasturchi va kod tahrirlovchi AI yordamchisisan.
Sening vazifang foydalanuvchiga kompyuterdagi loyihalarini boshqarishda, kodlarni tahlil qilishda, xatolarni tuzatishda (bug fixing), yangi funksiyalar yozishda va terminal buyruqlarini bajarishda yordam berish.
Javoblaringni aniq, tushunarli va professional o'zbek tilida ber. Kod bloklarini Markdown formatida chiroyli qilib yubor.
"""

AGENT_TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": "Fayl tarkibini to'liq o'qiydi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Faylning nisbiy yoki to'liq yo'li"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Faylga yangi kod/matn yozadi yoki faylni to'liq yangilaydi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Fayl yo'li"},
                "content": {"type": "STRING", "description": "Faylga yoziladigan to'liq matn/kod"}
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "replace_in_file",
        "description": "Fayl ichidagi aniq ko'rsatilgan qismni yangisiga almashtiradi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Fayl yo'li"},
                "target": {"type": "STRING", "description": "O'zgartirilishi kerak bo'lgan mavjud kod parchasi"},
                "replacement": {"type": "STRING", "description": "Yangi almashtiriladigan kod parchasi"}
            },
            "required": ["file_path", "target", "replacement"]
        }
    },
    {
        "name": "list_files",
        "description": "Papka ichidagi barcha fayllar va papkalar ro'yxatini ko'rsatadi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "directory": {"type": "STRING", "description": "Papka yo'li (bo'sh qoldirilsa joriy papka)"}
            }
        }
    },
    {
        "name": "execute_command",
        "description": "Terminalda PowerShell/CMD buyrug'ini bajaradi (masalan: pytest, npm test, python main.py, git status).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Bajariladigan terminal buyrug'i"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_code",
        "description": "Loyiha bo'ylab kalit so'z yoki funksiya nomini qidiradi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Qidirilayotgan so'z yoki kod"}
            },
            "required": ["query"]
        }
    }
]


class AIService:
    """Google Gemini va boshqa LLM lar bilan ishlash, AI Agent va kod tahrirlash xizmati."""

    @staticmethod
    def is_configured() -> bool:
        """AI API kaliti sozlanganligini tekshiradi."""
        return bool(GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY")

    @staticmethod
    def _get_client():
        """Google GenAI mijozini yaratadi."""
        if not AIService.is_configured():
            raise ValueError(
                "Gemini API kaliti kiritilmagan! Iltimos, .env fayliga GEMINI_API_KEY ni kiriting.\n"
                "Kalitni bu yerdan bepul olishingiz mumkin: https://aistudio.google.com/app/apikey"
            )
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEY)

    @staticmethod
    async def ask_ai(prompt: str, system_context: Optional[str] = None) -> str:
        """AI ga to'g'ridan-to'g'ri savol berish va javob olish."""
        try:
            client = AIService._get_client()
            full_system = SYSTEM_PROMPT
            if system_context:
                full_system += f"\nQo'shimcha kontekst:\n{system_context}"

            def _call():
                from google.genai import types
                response = client.models.generate_content(
                    model=AI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=full_system,
                        temperature=0.7,
                    )
                )
                return response.text

            result = await asyncio.to_thread(_call)
            return result or "AI bo'sh javob qaytardi."
        except Exception as e:
            logger.error(f"AI so'rovida xatolik: {e}")
            return f"❌ AI xatosi: {str(e)}"

    @staticmethod
    async def explain_code(file_path: Path) -> str:
        """Fayldagi kodni tahlil qilib, uning ishlash mexanizmini tushuntiradi."""
        try:
            content, _ = await FileService.read_file(file_path, max_length=15000)
            prompt = (
                f"Quyidagi `{file_path.name}` faylidagi kodni tahlil qil va uning asosiy vazifasi, "
                f"ishlash prinsipi va arxitekturasini o'zbek tilida ravon va qisqa tushuntirib ber:\n\n"
                f"```{file_path.suffix.lstrip('.')}\n{content}\n```"
            )
            return await AIService.ask_ai(prompt)
        except Exception as e:
            return f"❌ Faylni tahlil qilishda xatolik: {str(e)}"

    @staticmethod
    async def review_code(file_path: Path) -> str:
        """Kodni xavfsizlik, tozalik va optimizatsiya bo'yicha ko'rib chiqadi."""
        try:
            content, _ = await FileService.read_file(file_path, max_length=15000)
            prompt = (
                f"Quyidagi `{file_path.name}` faylidagi kodni Code Review qil:\n"
                f"1. Xavfsizlik zaifliklari (Security Issues)\n"
                f"2. Ishlash tezligi va optimizatsiya (Performance)\n"
                f"3. Kod tozaligi va Clean Code standartlari\n"
                f"4. Yaxshilash bo'yicha tavsiyalar\n\n"
                f"Fayl kodi:\n```{file_path.suffix.lstrip('.')}\n{content}\n```"
            )
            return await AIService.ask_ai(prompt)
        except Exception as e:
            return f"❌ Code Review xatosi: {str(e)}"

    @staticmethod
    async def fix_code(file_path: Path, issue_description: str, auto_apply: bool = False) -> tuple[str, bool]:
        """
        Koddagi xatolikni aniqlaydi va tuzatadi.
        Agar auto_apply=True bo'lsa, tuzatilgan kodni faylga to'g'ridan-to'g'ri yozadi.
        """
        try:
            content, _ = await FileService.read_file(file_path, max_length=20000)
            prompt = (
                f"Fayl: `{file_path.name}`\n"
                f"Foydalanuvchi aytgan muammo: {issue_description}\n\n"
                f"Mavjud kod:\n```{file_path.suffix.lstrip('.')}\n{content}\n```\n\n"
                f"Vazifa:\n"
                f"1. Xatoni tushuntir.\n"
                f"2. Qanday tuzatilganini ko'rsat.\n"
                f"3. Pastda ```fixed_code ... ``` blokida faylning to'liq TUZATILGAN kodini yozib ber."
            )
            ai_response = await AIService.ask_ai(prompt)

            applied = False
            if auto_apply and "```fixed_code" in ai_response:
                try:
                    parts = ai_response.split("```fixed_code")
                    fixed_code_part = parts[1].split("```")[0].strip()
                    if fixed_code_part:
                        await FileService.write_file(file_path, fixed_code_part, overwrite=True)
                        applied = True
                except Exception as write_err:
                    logger.error(f"Tuzatilgan kodni saqlashda xatolik: {write_err}")

            return ai_response, applied
        except Exception as e:
            return f"❌ Kodni tuzatishda xatolik: {str(e)}", False

    @staticmethod
    async def run_autonomous_agent(
        instruction: str,
        cwd: Path,
        progress_callback: Optional[Callable[[str], None]] = None,
        max_steps: int = 6
    ) -> str:
        """
        Avtonom AI Coding Agent tsikli (ReAct - Reason, Act, Observe).
        Agent fayllarni o'qiydi, tahrirlaydi, buyruqlarni bajaradi va natijani hisobot qiladi.
        """
        if not AIService.is_configured():
            return (
                "❌ <b>AI API kaliti topilmadi!</b>\n\n"
                "AI Agentdan foydalanish uchun <code>.env</code> fayliga <code>GEMINI_API_KEY</code> kiriting.\n"
                "Bepul API kalit olish: https://aistudio.google.com/app/apikey"
            )

        client = AIService._get_client()
        from google.genai import types

        agent_system = (
            f"{SYSTEM_PROMPT}\n"
            f"Sen hozir avtonom agent rejimidasan. Loyihaning joriy papkasi: `{cwd}`\n"
            f"Senga quyidagi maxsus asboblar (tools) berilgan:\n"
            f"- read_file(file_path)\n"
            f"- write_file(file_path, content)\n"
            f"- replace_in_file(file_path, target, replacement)\n"
            f"- list_files(directory)\n"
            f"- execute_command(command)\n"
            f"- search_code(query)\n\n"
            f"Vazifani bajarish uchun zarur vositalardan foydalan. Ishni to'liq tugatganingda barcha o'zgarishlar va natijalarni o'zbek tilida chiroyli xulosa qilib ber."
        )

        conversation_history = [
            {"role": "user", "parts": [f"Vazifa: {instruction}"]}
        ]

        action_log = []

        for step in range(1, max_steps + 1):
            if progress_callback:
                try:
                    progress_callback(f"🤖 AI Agent qadam {step}/{max_steps} bajarmoqda...")
                except Exception:
                    pass

            def _step_call():
                return client.models.generate_content(
                    model=AI_MODEL,
                    contents=conversation_history,
                    config=types.GenerateContentConfig(
                        system_instruction=agent_system,
                        temperature=0.3,
                        tools=[
                            types.Tool(function_declarations=[
                                types.FunctionDeclaration(
                                    name="read_file",
                                    description="Faylni o'qish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={"file_path": types.Schema(type="STRING", description="Fayl yo'li")},
                                        required=["file_path"]
                                    )
                                ),
                                types.FunctionDeclaration(
                                    name="write_file",
                                    description="Faylga yozish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={
                                            "file_path": types.Schema(type="STRING", description="Fayl yo'li"),
                                            "content": types.Schema(type="STRING", description="Yoziladigan matn")
                                        },
                                        required=["file_path", "content"]
                                    )
                                ),
                                types.FunctionDeclaration(
                                    name="replace_in_file",
                                    description="Fayl ichidagi matnni almashtirish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={
                                            "file_path": types.Schema(type="STRING", description="Fayl yo'li"),
                                            "target": types.Schema(type="STRING", description="Eski matn"),
                                            "replacement": types.Schema(type="STRING", description="Yangi matn")
                                        },
                                        required=["file_path", "target", "replacement"]
                                    )
                                ),
                                types.FunctionDeclaration(
                                    name="list_files",
                                    description="Papka ichidagi fayllarni ko'rish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={"directory": types.Schema(type="STRING", description="Papka yo'li")},
                                    )
                                ),
                                types.FunctionDeclaration(
                                    name="execute_command",
                                    description="Terminal buyrug'ini ishga tushirish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={"command": types.Schema(type="STRING", description="Terminal buyrug'i")},
                                        required=["command"]
                                    )
                                ),
                                types.FunctionDeclaration(
                                    name="search_code",
                                    description="Loyiha ichidan qidirish",
                                    parameters=types.Schema(
                                        type="OBJECT",
                                        properties={"query": types.Schema(type="STRING", description="Qidiruv so'zi")},
                                        required=["query"]
                                    )
                                ),
                            ])
                        ]
                    )
                )

            try:
                response = await asyncio.to_thread(_step_call)
            except Exception as e:
                logger.error(f"Agent qadamida xatolik: {e}")
                return f"❌ AI Agent xatosi: {str(e)}"

            # Function call bormi tekshirish
            function_calls = []
            if response.function_calls:
                function_calls = response.function_calls
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            function_calls.append(part.function_call)

            if not function_calls:
                # Agar agent boshqa tool chaqirmasa, xulosani qaytaramiz
                summary = response.text or "Vazifa bajarildi."
                return summary

            # Asboblarni bajarish
            for fc in function_calls:
                fn_name = fc.name
                fn_args = fc.args or {}
                tool_result = ""

                logger.info(f"AI Agent Tool Call: {fn_name}({fn_args})")
                action_log.append(f"🔧 <b>{fn_name}</b>: <code>{fn_args}</code>")

                try:
                    if fn_name == "read_file":
                        target_file = FileService.resolve_path(cwd, fn_args.get("file_path", ""))
                        content, truncated = await FileService.read_file(target_file, max_length=8000)
                        tool_result = content if not truncated else content + "\n...[truncated]"

                    elif fn_name == "write_file":
                        target_file = FileService.resolve_path(cwd, fn_args.get("file_path", ""))
                        bytes_written = await FileService.write_file(target_file, fn_args.get("content", ""))
                        tool_result = f"Muvaffaqiyatli yozildi ({bytes_written} bayt): {target_file.name}"

                    elif fn_name == "replace_in_file":
                        target_file = FileService.resolve_path(cwd, fn_args.get("file_path", ""))
                        ok = await FileService.replace_in_file(
                            target_file,
                            fn_args.get("target", ""),
                            fn_args.get("replacement", "")
                        )
                        tool_result = "Muvaffaqiyatli almashtirildi." if ok else "Xato: ko'rsatilgan target matni topilmadi."

                    elif fn_name == "list_files":
                        target_dir = FileService.resolve_path(cwd, fn_args.get("directory", "."))
                        items = FileService.list_directory(target_dir)
                        tool_result = "\n".join([f"{item['icon']} {item['name']} ({item['size_formatted']})" for item in items])

                    elif fn_name == "execute_command":
                        cmd_res = await TerminalService.execute_command(fn_args.get("command", ""), cwd=cwd, timeout=60)
                        tool_result = f"Exit code: {cmd_res['exit_code']}\nSTDOUT:\n{cmd_res['stdout']}\nSTDERR:\n{cmd_res['stderr']}"

                    elif fn_name == "search_code":
                        matches = FileService.search_code(fn_args.get("query", ""), cwd)
                        tool_result = json.dumps(matches, indent=2, ensure_ascii=False)

                    else:
                        tool_result = f"Noma'lum asbob: {fn_name}"

                except Exception as tool_err:
                    tool_result = f"Asbobni bajarishda xatolik: {str(tool_err)}"

                # Kontekstga natijani qo'shish
                conversation_history.append({
                    "role": "model",
                    "parts": [f"Chaqirilgan asbob: {fn_name}({fn_args})"]
                })
                conversation_history.append({
                    "role": "user",
                    "parts": [f"Asbob natijasi ({fn_name}):\n{tool_result}"]
                })

        return "⚠️ Agent ruxsat etilgan maksimal qadamlar soniga yetdi. Joriy holatni fayllar bo'limidan tekshirishingiz mumkin."
