from PIL import Image, ImageDraw, ImageFont, ImageFilter
import aiohttp
import io
from pathlib import Path

class RankCardGenerator:
    """Generate rank card images similar to popular bots like YC45/Arcane"""
    
    def __init__(self):
        self.width = 900
        self.height = 300
        self.bg_color = (30, 30, 40)  # Dark background
        self.accent_color = (88, 101, 242)  # Discord blurple
        self.text_color = (255, 255, 255)
        self.secondary_text_color = (180, 180, 180)
        
    async def fetch_avatar(self, avatar_url: str):
        """Fetch user avatar from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(io.BytesIO(data))
        except Exception as e:
            print(f"Error fetching avatar: {e}")
        return None
    
    def create_circular_avatar(self, avatar: Image.Image, size: int = 120):
        """Create a circular avatar with border"""
        # Resize avatar
        avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
        
        # Create circular mask
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        
        # Apply mask
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(avatar, (0, 0))
        output.putalpha(mask)
        
        return output
    
    def get_font(self, size: int, bold: bool = False):
        """Get font with fallback options"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
        
        # Fallback to default font
        return ImageFont.load_default()
    
    def draw_rounded_rectangle(self, draw, xy, radius, fill=None, outline=None, width=1):
        """Draw a rounded rectangle"""
        x1, y1, x2, y2 = xy
        
        # Draw the main rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline)
        
        # Draw the corners
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill, outline=outline)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill, outline=outline)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill, outline=outline)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill, outline=outline)
    
    async def generate_rank_card(
        self,
        avatar_url: str,
        username: str,
        rank: int,
        level: int,
        current_xp: int,
        required_xp: int,
        total_xp: int,
        messages: int,
        accent_color: tuple = None
    ):
        """Generate a rank card image"""
        
        # Create base image
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Use custom accent color if provided
        if accent_color:
            self.accent_color = accent_color
        
        # Draw main card background with rounded corners
        card_margin = 20
        self.draw_rounded_rectangle(
            draw,
            [card_margin, card_margin, self.width - card_margin, self.height - card_margin],
            radius=15,
            fill=(40, 40, 50)
        )
        
        # Fetch and draw avatar
        avatar_image = await self.fetch_avatar(avatar_url)
        if avatar_image:
            avatar = self.create_circular_avatar(avatar_image, size=140)
            avatar_x = 50
            avatar_y = (self.height - 140) // 2
            
            # Draw avatar border
            draw.ellipse(
                [avatar_x - 5, avatar_y - 5, avatar_x + 145, avatar_y + 145],
                outline=self.accent_color,
                width=4
            )
            
            # Paste avatar
            img.paste(avatar, (avatar_x, avatar_y), avatar)
        
        # Starting position for text (after avatar)
        text_start_x = 220
        
        # Get fonts
        font_username = self.get_font(45, bold=True)
        font_large = self.get_font(40, bold=True)
        font_medium = self.get_font(30, bold=True)
        font_small = self.get_font(22)
        
        # Draw username
        draw.text((text_start_x, 40), username, font=font_username, fill=self.text_color)
        
        # Draw rank and level on same line
        stats_y = 100
        draw.text((text_start_x, stats_y), f"RANK #{rank}", font=font_medium, fill=self.accent_color)
        
        # Calculate rank text width to position level next to it
        rank_text_width = draw.textbbox((text_start_x, stats_y), f"RANK #{rank}", font=font_medium)[2] - text_start_x
        level_x = text_start_x + rank_text_width + 40
        
        draw.text((level_x, stats_y), f"LEVEL {level}", font=font_medium, fill=self.text_color)
        
        # Draw XP progress bar
        progress_y = 160
        bar_width = self.width - text_start_x - 50
        bar_height = 35
        
        # Background bar
        self.draw_rounded_rectangle(
            draw,
            [text_start_x, progress_y, text_start_x + bar_width, progress_y + bar_height],
            radius=17,
            fill=(25, 25, 35)
        )
        
        # Progress bar
        progress_percent = current_xp / required_xp if required_xp > 0 else 0
        progress_width = int(bar_width * progress_percent)
        
        if progress_width > 0:
            self.draw_rounded_rectangle(
                draw,
                [text_start_x, progress_y, text_start_x + progress_width, progress_y + bar_height],
                radius=17,
                fill=self.accent_color
            )
        
        # Draw progress text inside bar
        progress_text = f"{current_xp:,} / {required_xp:,} XP"
        progress_bbox = draw.textbbox((0, 0), progress_text, font=font_small)
        progress_text_width = progress_bbox[2] - progress_bbox[0]
        progress_text_x = text_start_x + (bar_width - progress_text_width) // 2
        progress_text_y = progress_y + (bar_height - (progress_bbox[3] - progress_bbox[1])) // 2
        
        draw.text((progress_text_x, progress_text_y), progress_text, font=font_small, fill=self.text_color)
        
        # Draw additional stats
        stats_y2 = progress_y + bar_height + 20
        stats_text = f"Total XP: {total_xp:,}  •  Messages: {messages:,}  •  {progress_percent * 100:.1f}%"
        draw.text((text_start_x, stats_y2), stats_text, font=font_small, fill=self.secondary_text_color)
        
        return img
    
    def save_to_bytes(self, image: Image.Image) -> io.BytesIO:
        """Convert image to bytes for Discord"""
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
