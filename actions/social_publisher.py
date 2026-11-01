import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from core import confirm

_BASE_DIR = Path(__file__).resolve().parent.parent
_PROFILE_DIR = _BASE_DIR / "workspace" / "browser_profile_instagram"
_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def _post_to_instagram(media_path: str, caption: str) -> str:
    """Automates publishing a photo or video to Instagram Web."""
    resolved_path = Path(media_path).resolve().as_posix()
    if not Path(media_path).exists():
        return f"Media file not found at: {media_path}"

    safe_path = json.dumps(resolved_path)
    safe_caption = json.dumps(caption)
    safe_profile = json.dumps(_PROFILE_DIR.as_posix())

    script = f'''
import asyncio
from playwright.async_api import async_playwright

async def post():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir={safe_profile},
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
            ],
            ignore_default_args=["--enable-automation"],
        )
        try:
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {{{{get: () => undefined}}}})"
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            # Dismiss 'Turn on Notifications' popup if it appears
            not_now = page.locator('button:has-text("Not Now")').first
            if await not_now.is_visible():
                await not_now.click()
                await page.wait_for_timeout(1000)

            # 1. Click Create / New Post button in sidebar
            create_btn = page.locator('svg[aria-label="New post"], svg[aria-label="Create"]').first
            await create_btn.click()
            await page.wait_for_timeout(1500)

            # If a submenu pops up asking "Post" vs "Live video", click "Post"
            post_submenu = page.locator('span:text-is("Post")').first
            if await post_submenu.is_visible():
                await post_submenu.click()
                await page.wait_for_timeout(1500)

            # 2. Upload file via the file input
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files({safe_path})
            await page.wait_for_timeout(3000)

            # Handle 'Video posts are now shared as reels' OK popup if uploading video
            ok_btn = page.locator('button:has-text("OK")').first
            if await ok_btn.is_visible():
                await ok_btn.click()
                await page.wait_for_timeout(1000)

            # 3. Click Next on Crop screen
            next_btn = page.locator('div[role="button"]:text-is("Next")').first
            await next_btn.wait_for(state="visible", timeout=15000)
            await next_btn.click()
            await page.wait_for_timeout(2000)

            # 4. Click Next on Filter/Edit screen
            next_btn = page.locator('div[role="button"]:text-is("Next")').first
            await next_btn.wait_for(state="visible", timeout=15000)
            await next_btn.click()
            await page.wait_for_timeout(2000)

            # 5. Fill caption
            caption_box = page.locator('div[aria-label="Write a caption..."], div[role="textbox"]').first
            await caption_box.wait_for(state="visible", timeout=15000)
            await caption_box.click()
            await caption_box.fill({safe_caption})
            await page.wait_for_timeout(1500)

            # 6. Click Share
            share_btn = page.locator('div[role="button"]:text-is("Share")').first
            await share_btn.click()

            # Wait until "Post shared" confirmation or 10 seconds
            await page.wait_for_timeout(10000)
        finally:
            await context.close()

asyncio.run(post())
'''
    try:
        res = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if res.returncode == 0:
            return "Successfully published post to Instagram."
        err_tail = res.stderr.strip()[-500:] if res.stderr else "Unknown error"
        return f"Instagram publish failed: {err_tail}"
    except subprocess.TimeoutExpired:
        return "Instagram publish timed out after 3 minutes."
    except Exception as e:
        return f"Error executing Instagram publisher: {e}"


def social_publisher(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
    **kwargs,
) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).lower().strip()
    platform_name = str(params.get("platform", "instagram")).lower().strip()
    media_path = str(params.get("media_path", "")).strip()
    caption = str(params.get("caption", "")).strip()

    if player:
        player.write_log(f"[Social] {action} on {platform_name}")

    if action != "post":
        return f"Unknown action: '{action}'. Use action='post' to publish."

    if not media_path:
        return "Please provide a valid 'media_path' pointing to an image or video file."

    if not Path(media_path).exists():
        return f"File does not exist at: {media_path}"

    if platform_name != "instagram":
        return f"Unsupported platform: '{platform_name}'. Currently supported: instagram."

    # Irreversible action check: publishing to a public social account requires HUD confirmation
    if confirm.pending_title():
        return "There is already a confirmation waiting on screen. Please resolve it first."

    def _execute():
        if speak:
            speak("Publishing your post to Instagram now, sir.")
        return _post_to_instagram(media_path, caption)

    return confirm.request(
        key="instagram_post",
        title=f"Publish to Instagram",
        detail=f"Media: {media_path}\nCaption: {caption[:200] + ('...' if len(caption) > 200 else '')}",
        run=_execute,
    )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "social_publisher",
    "description": (
        "Publishes photos or videos to social media accounts (like Instagram). "
        "Requires explicit confirmation on the HUD before publishing. "
        "Action must be 'post', and 'media_path' must point to a valid local file."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'post' to upload and share content"
            },
            "platform": {
                "type": "STRING",
                "description": "Target platform: 'instagram' (default: instagram)"
            },
            "media_path": {
                "type": "STRING",
                "description": "Full local file path to the image or video to be uploaded"
            },
            "caption": {
                "type": "STRING",
                "description": "Post caption or text description"
            }
        },
        "required": [
            "action",
            "media_path"
        ]
    },
    "handler": social_publisher,
}