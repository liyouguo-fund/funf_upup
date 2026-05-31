"""
发送邮件通知脚本
用于 GitHub Actions 中发送分析报告邮件
"""

import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime


def send_email():
    """发送邮件"""
    # 读取配置
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '465'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    recipients = os.environ.get('RECIPIENTS', '')
    job_status = os.environ.get('JOB_STATUS', 'success')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')

    if not smtp_user or not smtp_password or not recipients:
        print('SMTP配置不完整，跳过邮件发送')
        return False

    recipient_list = [r.strip() for r in recipients.split(',') if r.strip()]

    # 构建邮件
    msg = MIMEMultipart('alternative')
    msg['From'] = smtp_user
    msg['To'] = ', '.join(recipient_list)

    today = datetime.now().strftime('%Y年%m月%d日')
    task_link = f'{server_url}/{repo}/actions/runs/{run_id}'

    if job_status == 'success':
        msg['Subject'] = f'✅ 基金趋势分析报告 - {today}'

        # 尝试读取生成的HTML邮件正文
        html_body = ''
        html_path = 'output/宽基指数邮件正文.html'
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html_body = f.read()

        if html_body:
            # 在HTML中嵌入任务链接
            link_html = f'<p style="margin-top:20px;font-size:12px;color:#999;">任务链接: <a href="{task_link}">{task_link}</a></p>'
            html_body = html_body.replace('</body>', link_html + '</body>')
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        else:
            text = f'''基金趋势分析任务已完成！

分析内容：
- 场外基金趋势分析（WMA版本）
- 宽基指数趋势分析（EMA版本）

详细报告请查看 GitHub Actions Artifacts。
任务链接: {task_link}
'''
            msg.attach(MIMEText(text, 'plain', 'utf-8'))
    else:
        msg['Subject'] = f'❌ 基金分析任务失败 - {today}'
        text = f'''基金分析任务失败，请检查GitHub Actions日志。

任务链接: {task_link}
'''
        msg.attach(MIMEText(text, 'plain', 'utf-8'))

    # 尝试附加Excel报告
    for fname in ['output/基金与指数趋势分析.xlsx', 'output/基金趋势分析.xlsx', 'output/宽基指数趋势分析.xlsx']:
        if os.path.exists(fname):
            try:
                with open(fname, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(fname)}')
                    msg.attach(part)
            except Exception as e:
                print(f'附加文件失败 {fname}: {e}')

    # 发送邮件
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipient_list, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, recipient_list, msg.as_string())
        print(f'邮件发送成功！收件人: {recipients}')
        return True
    except Exception as e:
        print(f'邮件发送失败: {e}')
        return False


if __name__ == '__main__':
    success = send_email()
    sys.exit(0 if success else 1)
