#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本
"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from utils.config import AccountConfig, AppConfig, load_accounts_config
from utils.notify import get_notify

load_dotenv()

BALANCE_HASH_FILE = 'balance_hash.txt'


def load_balance_hash():
	"""加载余额hash"""
	try:
		if os.path.exists(BALANCE_HASH_FILE):
			with open(BALANCE_HASH_FILE, 'r', encoding='utf-8') as f:
				return f.read().strip()
	except Exception:
		pass
	return None


def save_balance_hash(balance_hash):
	"""保存余额hash"""
	try:
		with open(BALANCE_HASH_FILE, 'w', encoding='utf-8') as f:
			f.write(balance_hash)
	except Exception as e:
		print(f'Warning: Failed to save balance hash: {e}')


def generate_balance_hash(balances):
	"""生成余额数据的hash"""
	# 将包含 quota 和 used 的结构转换为简单的 quota 值用于 hash 计算
	simple_balances = {k: v['quota'] for k, v in balances.items()} if balances else {}
	balance_json = json.dumps(simple_balances, sort_keys=True, separators=(',', ':'))
	return hashlib.sha256(balance_json.encode('utf-8')).hexdigest()[:16]


def parse_cookies(cookies_data):
	"""解析 cookies 数据"""
	if isinstance(cookies_data, dict):
		return cookies_data

	if isinstance(cookies_data, str):
		cookies_dict = {}
		for cookie in cookies_data.split(';'):
			if '=' in cookie:
				key, value = cookie.strip().split('=', 1)
				cookies_dict[key] = value
		return cookies_dict
	return {}


async def get_waf_cookies_with_playwright(account_name: str, login_url: str):
	"""使用 Playwright 获取 WAF cookies（隐私模式）"""
	print(f'[PROCESSING] {account_name}: Starting browser to get WAF cookies...')

	async with async_playwright() as p:
		import tempfile

		with tempfile.TemporaryDirectory() as temp_dir:
			context = await p.chromium.launch_persistent_context(
				user_data_dir=temp_dir,
				headless=False,
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				viewport={'width': 1920, 'height': 1080},
				args=[
					'--disable-blink-features=AutomationControlled',
					'--disable-dev-shm-usage',
					'--disable-web-security',
					'--disable-features=VizDisplayCompositor',
					'--no-sandbox',
				],
			)

			page = await context.new_page()

			try:
				print(f'[PROCESSING] {account_name}: Access login page to get initial cookies...')

				await page.goto(login_url, wait_until='networkidle')

				try:
					await page.wait_for_function('document.readyState === "complete"', timeout=5000)
				except Exception:
					await page.wait_for_timeout(3000)

				cookies = await page.context.cookies()

				waf_cookies = {}
				for cookie in cookies:
					cookie_name = cookie.get('name')
					cookie_value = cookie.get('value')
					if cookie_name in ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'] and cookie_value is not None:
						waf_cookies[cookie_name] = cookie_value

				print(f'[INFO] {account_name}: Got {len(waf_cookies)} WAF cookies: {list(waf_cookies.keys())}')

				# 灵活的检测策略：只要获取到至少一个 WAF cookie 就算成功
				if not waf_cookies:
					print(f'[FAILED] {account_name}: No WAF cookies obtained')
					await context.close()
					return None

				# 记录缺失的 cookies（仅作为提示，不影响成功判断）
				expected_cookies = ['acw_tc', 'cdn_sec_tc', 'acw_sc__v2']
				missing_cookies = [c for c in expected_cookies if c not in waf_cookies]
				if missing_cookies:
					print(f'[INFO] {account_name}: Some cookies not found (may not be required): {missing_cookies}')

				print(f'[SUCCESS] {account_name}: Successfully got WAF cookies')

				await context.close()

				return waf_cookies

			except Exception as e:
				print(f'[FAILED] {account_name}: Error occurred while getting WAF cookies: {e}')
				await context.close()
				return None


def get_user_info(client, headers, user_info_url: str, account_name: str = ''):
	"""获取用户信息"""
	try:
		response = client.get(user_info_url, headers=headers, timeout=30)

		# 添加详细日志用于诊断
		if account_name:
			print(f'[DEBUG] {account_name}: Response status: {response.status_code}')
			print(f'[DEBUG] {account_name}: Content-Type: {response.headers.get("Content-Type", "Unknown")}')
			print(f'[DEBUG] {account_name}: Response preview: {response.text[:300]}...')

		if response.status_code == 200:
			# 首先尝试解析 JSON，失败后再检查是否是 HTML 验证页面
			try:
				data = response.json()
				if data.get('success'):
					user_data = data.get('data', {})
					quota = round(user_data.get('quota', 0) / 500000, 2)
					used_quota = round(user_data.get('used_quota', 0) / 500000, 2)
					return {
						'success': True,
						'quota': quota,
						'used_quota': used_quota,
						'display': f':money: Current balance: ${quota}, Used: ${used_quota}',
					}
			except json.JSONDecodeError:
				# JSON 解析失败，检查是否是 HTML 验证页面
				content_type = response.headers.get('Content-Type', '').lower()
				response_text = response.text.lower()

				# 检测是否为 WAF 验证页面
				if ('html' in content_type or
					'<html' in response_text[:100] or
					'verification' in response_text[:200] or
					'cloudflare' in response_text[:200] or
					'acw_tc' in response_text[:200] or
					'sorry, you have been blocked' in response_text or
					'access denied' in response_text):

					print(f'[WARNING] {account_name}: WAF verification page detected')
					return {'success': False, 'error': 'WAF verification page detected'}
				else:
					# 不是验证页面，但解析 JSON 失败
					print(f'[ERROR] {account_name}: Invalid response format (not JSON, not HTML verification)')
					return {'success': False, 'error': 'Invalid response format'}

		return {'success': False, 'error': f'Failed to get user info: HTTP {response.status_code}'}
	except Exception as e:
		return {'success': False, 'error': f'Failed to get user info: {str(e)[:50]}...'}


async def prepare_cookies(account_name: str, provider_config, user_cookies: dict) -> dict | None:
	"""准备请求所需的 cookies（可能包含 WAF cookies）"""
	waf_cookies = {}

	if provider_config.needs_waf_cookies():
		login_url = f'{provider_config.domain}{provider_config.login_path}'
		waf_cookies = await get_waf_cookies_with_playwright(account_name, login_url)
		if not waf_cookies:
			print(f'[FAILED] {account_name}: Unable to get WAF cookies')
			return None
	else:
		print(f'[INFO] {account_name}: Using user cookies directly (no WAF bypass needed)')

	return {**waf_cookies, **user_cookies}


def execute_check_in(client, account_name: str, provider_config, headers: dict):
	"""执行签到请求"""
	print(f'[NETWORK] {account_name}: Executing check-in')

	checkin_headers = headers.copy()
	checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})

	sign_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'
	response = client.post(sign_in_url, headers=checkin_headers, timeout=30)

	print(f'[RESPONSE] {account_name}: Response status code {response.status_code}')

	if response.status_code == 200:
		try:
			result = response.json()
			if result.get('ret') == 1 or result.get('code') == 0 or result.get('success'):
				print(f'[SUCCESS] {account_name}: Check-in successful!')
				return True
			else:
				error_msg = result.get('msg', result.get('message', 'Unknown error'))
				print(f'[FAILED] {account_name}: Check-in failed - {error_msg}')
				return False
		except json.JSONDecodeError:
			# 如果不是 JSON 响应，检查是否包含成功标识
			if 'success' in response.text.lower():
				print(f'[SUCCESS] {account_name}: Check-in successful!')
				return True
			else:
				print(f'[FAILED] {account_name}: Check-in failed - Invalid response format')
				return False
	else:
		print(f'[FAILED] {account_name}: Check-in failed - HTTP {response.status_code}')
		return False


async def check_in_account(account: AccountConfig, account_index: int, app_config: AppConfig):
	"""为单个账号执行签到操作"""
	account_name = account.get_display_name(account_index)
	print(f'\n[PROCESSING] Starting to process {account_name}')

	provider_config = app_config.get_provider(account.provider)
	if not provider_config:
		print(f'[FAILED] {account_name}: Provider "{account.provider}" not found in configuration')
		return False, None

	print(f'[INFO] {account_name}: Using provider "{account.provider}" ({provider_config.domain})')

	user_cookies = parse_cookies(account.cookies)
	if not user_cookies:
		print(f'[FAILED] {account_name}: Invalid configuration format')
		return False, None

	# 重试配置
	max_retries = int(os.getenv('MAX_RETRIES', '2'))
	retry_delay = float(os.getenv('RETRY_DELAY', '5'))

	for attempt in range(max_retries + 1):
		if attempt > 0:
			print(f'[RETRY] {account_name}: Attempt {attempt + 1}/{max_retries + 1} after {retry_delay}s delay...')
			await asyncio.sleep(retry_delay)

		all_cookies = await prepare_cookies(account_name, provider_config, user_cookies)
		if not all_cookies:
			if attempt < max_retries:
				continue
			return False, None

		client = httpx.Client(http2=True, timeout=30.0)

		try:
			client.cookies.update(all_cookies)

			headers = {
				'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				'Accept': 'application/json, text/plain, */*',
				'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
				'Accept-Encoding': 'gzip, deflate, br, zstd',
				'Referer': provider_config.domain,
				'Origin': provider_config.domain,
				'Connection': 'keep-alive',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
				provider_config.api_user_key: account.api_user,
			}

			user_info_url = f'{provider_config.domain}{provider_config.user_info_path}'
			user_info = get_user_info(client, headers, user_info_url, account_name)

			# 检查是否因为 WAF 失败
			if user_info and not user_info.get('success'):
				error = user_info.get('error', '')
				if ('WAF' in error or
					'verification' in error.lower() or
					'HTML' in error):
					if attempt < max_retries:
						print(f'[WARNING] {account_name}: WAF/verification detected, will retry...')
						client.close()
						continue

			if user_info and user_info.get('success'):
				print(user_info['display'])
			elif user_info:
				print(user_info.get('error', 'Unknown error'))

			if provider_config.needs_manual_check_in():
				success = execute_check_in(client, account_name, provider_config, headers)
				return success, user_info
			else:
				print(f'[INFO] {account_name}: Check-in completed automatically (triggered by user info request)')
				# 只有成功获取用户信息才算成功
				success = user_info and user_info.get('success', False)
				return success, user_info

		except Exception as e:
			print(f'[FAILED] {account_name}: Error occurred during check-in process - {str(e)[:50]}...')
			if attempt < max_retries:
				print(f'[WARNING] {account_name}: Exception occurred, will retry...')
				client.close()
				continue
			return False, None
		finally:
			client.close()

	# 所有重试都失败
	print(f'[FAILED] {account_name}: All retry attempts exhausted')
	return False, None


async def main():
	"""主函数"""
	print('[SYSTEM] AnyRouter.top multi-account auto check-in script started (using Playwright)')
	print(f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

	app_config = AppConfig.load_from_env()
	print(f'[INFO] Loaded {len(app_config.providers)} provider configuration(s)')

	accounts = load_accounts_config()
	if not accounts:
		print('[FAILED] Unable to load account configuration, program exits')
		sys.exit(1)

	print(f'[INFO] Found {len(accounts)} account configurations')

	# 配置：每个账号之间的延迟（秒）- GitHub Actions 环境建议使用更长的延迟
	DELAY_BETWEEN_ACCOUNTS = float(os.getenv('DELAY_BETWEEN_ACCOUNTS', '5'))
	print(f'[INFO] Delay between accounts: {DELAY_BETWEEN_ACCOUNTS} seconds')

	last_balance_hash = load_balance_hash()

	success_count = 0
	total_count = len(accounts)
	notification_content = []
	current_balances = {}
	need_notify = False  # 是否需要发送通知
	balance_changed = False  # 余额是否有变化

	# 用于构建 HTML 邮件的账号数据
	accounts_data = []

	for i, account in enumerate(accounts):
		account_key = f'account_{i + 1}'
		account_name = account.get_display_name(i)

		try:
			success, user_info = await check_in_account(account, i, app_config)
			if success:
				success_count += 1

			should_notify_this_account = False

			if not success:
				should_notify_this_account = True
				need_notify = True
				print(f'[NOTIFY] {account_name} failed, will send notification')

			if user_info and user_info.get('success'):
				current_quota = user_info['quota']
				current_used = user_info['used_quota']
				current_balances[account_key] = {'quota': current_quota, 'used': current_used}

				# 添加到 HTML 数据
				accounts_data.append({
					'name': account_name,
					'success': success,
					'quota': current_quota,
					'used_quota': current_used,
				})
			else:
				# 失败的账号
				error_msg = user_info.get('error', 'Unknown error') if user_info else 'Unknown error'
				accounts_data.append({
					'name': account_name,
					'success': False,
					'quota': 0,
					'used_quota': 0,
					'error': error_msg,
				})

			if should_notify_this_account:
				status = '[SUCCESS]' if success else '[FAIL]'
				account_result = f'{status} {account_name}'
				if user_info and user_info.get('success'):
					account_result += f'\n{user_info["display"]}'
				elif user_info:
					account_result += f'\n{user_info.get("error", "Unknown error")}'
				notification_content.append(account_result)

		except Exception as e:
			print(f'[FAILED] {account_name} processing exception: {e}')
			need_notify = True  # 异常也需要通知
			notification_content.append(f'[FAIL] {account_name} exception: {str(e)[:50]}...')

			# 添加异常账号到 HTML 数据
			accounts_data.append({
				'name': account_name,
				'success': False,
				'quota': 0,
				'used_quota': 0,
				'error': f'Exception: {str(e)[:100]}',
			})

		# 添加延迟，避免触发 WAF（最后一个账号不需要延迟）
		if i < len(accounts) - 1 and DELAY_BETWEEN_ACCOUNTS > 0:
			print(f'[INFO] Waiting {DELAY_BETWEEN_ACCOUNTS} seconds before processing next account...')
			await asyncio.sleep(DELAY_BETWEEN_ACCOUNTS)

	# 检查余额变化
	current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
	if current_balance_hash:
		if last_balance_hash is None:
			# 首次运行
			balance_changed = True
			need_notify = True
			print('[NOTIFY] First run detected, will send notification with current balances')
		elif current_balance_hash != last_balance_hash:
			# 余额有变化
			balance_changed = True
			need_notify = True
			print('[NOTIFY] Balance changes detected, will send notification')
		else:
			print('[INFO] No balance changes detected')

	# 为有余额变化的情况添加所有成功账号到通知内容
	if balance_changed:
		for i, account in enumerate(accounts):
			account_key = f'account_{i + 1}'
			if account_key in current_balances:
				account_name = account.get_display_name(i)
				# 只添加成功获取余额的账号，且避免重复添加
				account_result = f'[BALANCE] {account_name}'
				account_result += f'\n:money: Current balance: ${current_balances[account_key]["quota"]}, Used: ${current_balances[account_key]["used"]}'
				# 检查是否已经在通知内容中（避免重复）
				if not any(account_name in item for item in notification_content):
					notification_content.append(account_result)

	# 保存当前余额hash
	if current_balance_hash:
		save_balance_hash(current_balance_hash)

	if need_notify and notification_content:
		# 构建文本通知内容（用于非邮件通知渠道）
		summary = [
			'[STATS] Check-in result statistics:',
			f'[SUCCESS] Success: {success_count}/{total_count}',
			f'[FAIL] Failed: {total_count - success_count}/{total_count}',
		]

		if success_count == total_count:
			summary.append('[SUCCESS] All accounts check-in successful!')
		elif success_count > 0:
			summary.append('[WARN] Some accounts check-in successful')
		else:
			summary.append('[ERROR] All accounts check-in failed')

		time_info = f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

		notify_content = '\n\n'.join([time_info, '\n'.join(notification_content), '\n'.join(summary)])

		print(notify_content)

		# 构建 HTML 邮件数据
		html_data = {
			'accounts': accounts_data,
			'summary': {
				'total': total_count,
				'success_count': success_count,
				'failed_count': total_count - success_count,
				'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
			},
			'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
		}

		# 发送 HTML 邮件
		get_notify().send_html_email('AnyRouter 签到结果', html_data)

		# 发送其他通知（钉钉、飞书等），跳过邮件通知避免重复发送
		get_notify().push_message('AnyRouter Check-in Alert', notify_content, msg_type='text', skip_email=True)
		print('[NOTIFY] Notification sent due to failures or balance changes')
	else:
		print('[INFO] All accounts successful and no balance changes detected, notification skipped')

	# 设置退出码
	sys.exit(0 if success_count > 0 else 1)


def run_main():
	"""运行主函数的包装函数"""
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print('\n[WARNING] Program interrupted by user')
		sys.exit(1)
	except Exception as e:
		print(f'\n[FAILED] Error occurred during program execution: {e}')
		sys.exit(1)


if __name__ == '__main__':
	run_main()
