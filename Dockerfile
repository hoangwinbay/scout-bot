FROM python:3.11-slim

WORKDIR /app

# Cài đặt timezone chuẩn Việt Nam (GMT+7) để scheduler quét đúng giờ
ENV TZ=Asia/Ho_Chi_Minh
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-u", "app.py"]
