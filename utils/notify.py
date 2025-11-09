import os
import smtplib
from email.mime.text import MIMEText
from typing import Literal, Any

import httpx


# ==================== HTML 模板  ====================
DEFAULT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentRouter 签到结果</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #e2e8f0;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        @media screen and (max-width: 768px) {
            body {
                padding: 0;
            }
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.05);
            overflow: hidden;
        }
        @media screen and (max-width: 768px) {
            .container {
                border-radius: 0;
                box-shadow: none;
            }
        }
        .header {
            background: #fafbfc;
            color: #1e293b;
            padding: 40px 20px 30px;
            text-align: center;
            position: relative;
            overflow: hidden;
            border-bottom: 1px solid #f1f5f9;
        }
        @media screen and (max-width: 768px) {
            .header {
                padding: 30px 15px 20px;
            }
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
            font-weight: 700;
            position: relative;
            z-index: 1;
            text-shadow: none;
            letter-spacing: -0.02em;
            color: #0f172a;
        }
        @media screen and (max-width: 768px) {
            .header h1 {
                font-size: 22px;
            }
        }
        .summary {
            background-color: #ffffff;
            padding: 25px 20px;
            border-bottom: none;
        }
        .summary h2 {
            margin: 0 0 20px 0;
            font-size: 18px;
            color: #0f172a;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }
        @media screen and (max-width: 768px) {
            .summary {
                padding: 20px 16px;
            }
            .summary h2 {
                font-size: 17px;
                margin-bottom: 16px;
            }
            .stats {
                gap: 8px;
            }
        }
        .stat-item {
            padding: 18px 12px;
            background: #fafbfc;
            border-radius: 12px;
            border: 1px solid #f1f5f9;
            text-align: center;
            box-shadow: none;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .stat-item:active {
            transform: translateY(1px);
            background: #f1f5f9;
        }
        @media screen and (max-width: 768px) {
            .stat-item {
                padding: 14px 8px;
                border-radius: 10px;
            }
        }
        .stat-label {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 8px;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: -0.01em;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: #0f172a;
            line-height: 1;
            letter-spacing: -0.03em;
        }
        @media screen and (max-width: 768px) {
            .stat-label {
                font-size: 11px;
                margin-bottom: 5px;
            }
            .stat-value {
                font-size: 22px;
            }
        }
        .accounts {
            padding: 25px 20px 30px;
            background-color: #ffffff;
        }
        .accounts h2 {
            margin: 0 0 20px 0;
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.02em;
        }
        @media screen and (max-width: 768px) {
            .accounts {
                padding: 20px 16px 25px;
            }
            .accounts h2 {
                font-size: 17px;
                margin-bottom: 16px;
            }
        }
        .account {
            padding: 18px 20px;
            margin-bottom: 12px;
            border-radius: 12px;
            background-color: #fafbfc;
            border: 1px solid #f1f5f9;
            box-shadow: none;
            transition: transform 0.15s ease, background-color 0.15s ease;
        }
        .account:active {
            transform: translateY(1px);
            background-color: #f1f5f9;
        }
        @media screen and (max-width: 768px) {
            .account {
                padding: 16px 16px;
                margin-bottom: 10px;
                border-radius: 14px;
            }
        }
        .account.success {
            background: #fafbfc;
            border-left: 4px solid #10b981;
        }
        .account.failed {
            background: #fafbfc;
            border-left: 4px solid #ef4444;
        }
        .account-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .account-name {
            font-size: 15px;
            font-weight: 600;
            color: #333;
        }
        .account-status {
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 600;
            white-space: nowrap;
        }
        @media screen and (max-width: 768px) {
            .account-name {
                font-size: 14px;
                max-width: 60%;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .account-status {
                font-size: 11px;
                padding: 3px 8px;
            }
        }
        .status-success {
            background-color: #28a745;
            color: white;
        }
        .status-failed {
            background-color: #dc3545;
            color: white;
        }
        .account-detail {
            font-size: 13px;
            color: #666;
            line-height: 1.8;
            word-break: break-word;
        }
        .account-detail strong {
            color: #333;
            font-weight: 600;
        }
        @media screen and (max-width: 768px) {
            .account-detail {
                font-size: 12px;
                line-height: 1.6;
            }
        }
        .error-message {
            color: #dc3545;
            font-size: 13px;
            margin-top: 8px;
            padding: 10px 12px;
            background-color: rgba(220, 53, 69, 0.08);
            border-radius: 8px;
            border-left: 3px solid #dc3545;
            word-break: break-word;
        }
        @media screen and (max-width: 768px) {
            .error-message {
                font-size: 12px;
                padding: 8px 10px;
            }
        }
        .warning {
            background-color: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 15px;
        }
        @media screen and (max-width: 768px) {
            .warning {
                margin: 12px 12px;
                padding: 12px;
            }
        }
        .warning h3 {
            margin: 0 0 8px 0;
            color: #856404;
            font-size: 14px;
            font-weight: 600;
        }
        .warning p {
            margin: 5px 0;
            color: #856404;
            font-size: 13px;
            line-height: 1.5;
        }
        .warning ul {
            margin: 8px 0;
            padding-left: 18px;
        }
        .warning li {
            color: #856404;
            margin: 4px 0;
            font-size: 13px;
        }
        @media screen and (max-width: 768px) {
            .warning h3 {
                font-size: 13px;
            }
            .warning p, .warning li {
                font-size: 12px;
            }
        }
        .footer {
            background-color: #fafbfc;
            padding: 20px 20px;
            text-align: center;
            border-top: 1px solid #f1f5f9;
        }
        .footer p {
            margin: 4px 0;
            font-size: 12px;
            color: #666;
        }
        @media screen and (max-width: 768px) {
            .footer {
                padding: 12px 15px;
            }
            .footer p {
                font-size: 11px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔔 AgentRouter 签到结果</h1>
        </div>

        <div class="summary">
            <h2>📊 统计摘要</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">总账号数</div>
                    <div class="stat-value">{{ summary.total }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">成功</div>
                    <div class="stat-value" style="color: #10b981;">{{ summary.success_count }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">失败</div>
                    <div class="stat-value" style="color: #ef4444;">{{ summary.failed_count }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">成功率</div>
                    <div class="stat-value" style="color: #06b6d4;">{{ "%.0f"|format(summary.success_rate) }}%</div>
                </div>
            </div>
        </div>

        <div class="accounts">
            <h2>📋 账号详情</h2>
            {% for account in accounts %}
            <div class="account {% if account.success %}success{% else %}failed{% endif %}">
                <div class="account-header">
                    <div class="account-name">{{ account.name }}</div>
                    <div class="account-status {% if account.success %}status-success{% else %}status-failed{% endif %}">
                        {% if account.success %}✅ 成功{% else %}[FAIL] 失败{% endif %}
                    </div>
                </div>
                {% if account.success %}
                <div class="account-detail">
                    <strong>💰 余额:</strong> ${{ "%.2f"|format(account.quota) }} |
                    <strong>已用:</strong> ${{ "%.2f"|format(account.used_quota) }}
                </div>
                {% else %}
                <div class="error-message">
                    [WARNING] {{ account.error }}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        {% if cookie_expired_accounts %}
        <div class="warning">
            <h3>[WARNING] Cookie 过期警告</h3>
            <p>以下账号的 Cookie 已过期，请尽快更新以确保后续签到正常：</p>
            <ul>
            {% for account in cookie_expired_accounts %}
                <li><strong>{{ account }}</strong></li>
            {% endfor %}
            </ul>
            <p style="margin-top: 15px; font-size: 13px;">
                [INFO] 提示：请参考 README.md 中的「获取 Cookies」章节重新获取 Cookie 并更新 GitHub Secrets。
            </p>
        </div>
        {% endif %}

        <div class="footer">
            <p>⏰ 执行时间：{{ timestamp }}</p>
            <p style="color: #999;">🤖 由 AnyRouter Check-in 自动生成</p>
        </div>
    </div>
</body>
</html>
"""


class NotificationKit:
	def __init__(self):
		self.email_user: str = os.getenv('EMAIL_USER', '')
		self.email_pass: str = os.getenv('EMAIL_PASS', '')
		self.email_to: str = os.getenv('EMAIL_TO', '')
		self.smtp_server: str = os.getenv('CUSTOM_SMTP_SERVER', '')
		self.pushplus_token = os.getenv('PUSHPLUS_TOKEN')
		self.server_push_key = os.getenv('SERVERPUSHKEY')
		self.dingding_webhook = os.getenv('DINGDING_WEBHOOK')
		self.feishu_webhook = os.getenv('FEISHU_WEBHOOK')
		self.weixin_webhook = os.getenv('WEIXIN_WEBHOOK')
		self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
		self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

	def send_html_email(self, title: str, data: dict[str, Any]):
		"""发送 HTML 邮件（使用 jinja2 模板渲染）

		Args:
			title: 邮件标题
			data: 模板数据，需包含以下字段：
				- accounts: 账号列表 [{'name': str, 'success': bool, 'quota': float, 'used_quota': float, 'error': str}]
				- summary: 统计摘要 {'total': int, 'success_count': int, 'failed_count': int, 'success_rate': float}
				- timestamp: 执行时间 str
				- cookie_expired_accounts: Cookie 过期账号列表 (可选)
		"""
		if not self.email_user or not self.email_pass or not self.email_to:
			print('[INFO] 邮件通知未配置，跳过')
			return

		try:
			print('[INFO] 正在渲染邮件模板...')
			# 使用 jinja2 渲染 HTML 模板
			from jinja2 import Template
			template = Template(DEFAULT_HTML_TEMPLATE)
			html_content = template.render(**data)
			print('[INFO] [OK] 邮件模板渲染完成')

			# 创建邮件
			print('[INFO] 正在创建邮件...')
			msg = MIMEText(html_content, 'html', 'utf-8')
			msg['From'] = f'AnyRouter Assistant <{self.email_user}>'
			msg['To'] = self.email_to
			msg['Subject'] = title
			print('[INFO] [OK] 邮件创建完成')

			# 发送邮件
			smtp_server = self.smtp_server if self.smtp_server else f'smtp.{self.email_user.split("@")[1]}'
			print(f'[INFO] 正在连接 SMTP 服务器: {smtp_server}...')

			try:
				print(f'[INFO] 尝试使用 SMTP_SSL (端口 465)...')
				with smtplib.SMTP_SSL(smtp_server, 465, timeout=10) as server:
					print(f'[INFO] 正在登录...')
					server.login(self.email_user, self.email_pass)
					print(f'[INFO] 正在发送邮件...')
					server.send_message(msg)
				print(f'[INFO] [OK] 邮件通知发送成功 (SMTP_SSL:465)')
				return
			except Exception as e:
				error_str = str(e)
				# QQ邮箱在 SMTP_SSL 可能返回 (-1, b'\x00\x00\x00')，但邮件已发送成功
				if '(-1,' in error_str or "b'\\x00\\x00\\x00'" in error_str:
					print(f'[INFO] [OK] 邮件通知发送成功 (SMTP_SSL:465, QQ 邮箱兼容模式)')
					return
				# 其他错误，尝试 STARTTLS
				print(f'[WARNING] SMTP_SSL (465) 失败: {e}，尝试 STARTTLS')

			# 尝试 STARTTLS
			try:
				print(f'[INFO] 尝试使用 SMTP + STARTTLS (端口 587)...')
				with smtplib.SMTP(smtp_server, 587, timeout=10) as server:
					print(f'[INFO] 正在启动 TLS...')
					server.starttls()
					print(f'[INFO] 正在登录...')
					server.login(self.email_user, self.email_pass)
					print(f'[INFO] 正在发送邮件...')
					server.send_message(msg)
				print(f'[INFO] [OK] 邮件通知发送成功 (STARTTLS:587)')
			except Exception as e:
				error_str = str(e)
				# QQ邮箱等某些邮件服务器在发送成功后会返回 (-1, b'\x00\x00\x00')
				if '(-1,' in error_str or "b'\\x00\\x00\\x00'" in error_str:
					print(f'[INFO] [OK] 邮件通知发送成功 (STARTTLS:587, QQ 邮箱兼容模式)')
					return
				# 真实错误，抛出
				raise

		except Exception as e:
			print(f'[ERROR] 邮件发送失败: {e}')

	def send_email(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text'):
		if not self.email_user or not self.email_pass or not self.email_to:
			raise ValueError('Email configuration not set')

		# MIMEText 需要 'plain' 或 'html'，而不是 'text'
		mime_subtype = 'plain' if msg_type == 'text' else 'html'
		msg = MIMEText(content, mime_subtype, 'utf-8')
		msg['From'] = f'AnyRouter Assistant <{self.email_user}>'
		msg['To'] = self.email_to
		msg['Subject'] = title

		smtp_server = self.smtp_server if self.smtp_server else f'smtp.{self.email_user.split("@")[1]}'
		with smtplib.SMTP_SSL(smtp_server, 465) as server:
			server.login(self.email_user, self.email_pass)
			server.send_message(msg)

	def send_pushplus(self, title: str, content: str):
		if not self.pushplus_token:
			raise ValueError('PushPlus Token not configured')

		data = {'token': self.pushplus_token, 'title': title, 'content': content, 'template': 'html'}
		with httpx.Client(timeout=30.0) as client:
			client.post('http://www.pushplus.plus/send', json=data)

	def send_serverPush(self, title: str, content: str):
		if not self.server_push_key:
			raise ValueError('Server Push key not configured')

		data = {'title': title, 'desp': content}
		with httpx.Client(timeout=30.0) as client:
			client.post(f'https://sctapi.ftqq.com/{self.server_push_key}.send', json=data)

	def send_dingtalk(self, title: str, content: str):
		if not self.dingding_webhook:
			raise ValueError('DingTalk Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.dingding_webhook, json=data)

	def send_feishu(self, title: str, content: str):
		if not self.feishu_webhook:
			raise ValueError('Feishu Webhook not configured')

		data = {
			'msg_type': 'interactive',
			'card': {
				'elements': [{'tag': 'markdown', 'content': content, 'text_align': 'left'}],
				'header': {'template': 'blue', 'title': {'content': title, 'tag': 'plain_text'}},
			},
		}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.feishu_webhook, json=data)

	def send_wecom(self, title: str, content: str):
		if not self.weixin_webhook:
			raise ValueError('WeChat Work Webhook not configured')

		data = {'msgtype': 'text', 'text': {'content': f'{title}\n{content}'}}
		with httpx.Client(timeout=30.0) as client:
			client.post(self.weixin_webhook, json=data)

	def send_telegram(self, title: str, content: str):
		if not self.telegram_bot_token or not self.telegram_chat_id:
			raise ValueError('Telegram Bot Token or Chat ID not configured')

		message = f'<b>{title}</b>\n\n{content}'
		data = {'chat_id': self.telegram_chat_id, 'text': message, 'parse_mode': 'HTML'}
		url = f'https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage'
		with httpx.Client(timeout=30.0) as client:
			client.post(url, json=data)

	def push_message(self, title: str, content: str, msg_type: Literal['text', 'html'] = 'text', skip_email: bool = False):
		"""发送通知到所有配置的渠道

		Args:
			title: 通知标题
			content: 通知内容
			msg_type: 消息类型 ('text' 或 'html')
			skip_email: 是否跳过邮件通知（当已经单独发送 HTML 邮件时设置为 True）
		"""
		notifications = [
			('PushPlus', lambda: self.send_pushplus(title, content)),
			('Server Push', lambda: self.send_serverPush(title, content)),
			('DingTalk', lambda: self.send_dingtalk(title, content)),
			('Feishu', lambda: self.send_feishu(title, content)),
			('WeChat Work', lambda: self.send_wecom(title, content)),
			('Telegram', lambda: self.send_telegram(title, content)),
		]

		# 如果不跳过邮件，则添加邮件通知到列表开头
		if not skip_email:
			notifications.insert(0, ('Email', lambda: self.send_email(title, content, msg_type)))

		for name, func in notifications:
			try:
				func()
				print(f'[{name}]: Message push successful!')
			except Exception as e:
				print(f'[{name}]: Message push failed! Reason: {str(e)}')


# 延迟初始化单例（解决 .env 加载时机问题）
_notify_instance = None


def get_notify() -> NotificationKit:
	"""获取 NotificationKit 单例（延迟初始化）

	使用延迟初始化模式确保在调用时才创建实例，
	这样可以保证 load_dotenv() 已经执行，环境变量已经加载。

	Returns:
		NotificationKit: 通知工具单例实例
	"""
	global _notify_instance
	if _notify_instance is None:
		_notify_instance = NotificationKit()
	return _notify_instance
