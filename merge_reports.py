import pandas as pd
import os

# 读取场外基金数据
fund_df = pd.read_excel('基金趋势分析.xlsx')

# 读取宽基指数数据
index_df = pd.read_excel('宽基指数趋势分析.xlsx')

# 合并到一个工作簿
with pd.ExcelWriter('基金与指数趋势分析.xlsx', engine='openpyxl') as writer:
    fund_df.to_excel(writer, sheet_name='场外基金', index=False)
    index_df.to_excel(writer, sheet_name='宽基指数', index=False)

print('整合报告已生成: 基金与指数趋势分析.xlsx')
