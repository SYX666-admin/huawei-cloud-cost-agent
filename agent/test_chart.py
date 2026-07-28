import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('demo/sample_bill.csv')
category_data = df.groupby('产品类型')['费用'].sum()
print(category_data)

plt.figure(figsize=(8, 6))
category_data.plot(kind='pie', autopct='%1.1f%%')
plt.title('费用分类占比')
plt.show()