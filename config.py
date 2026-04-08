import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-12345'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, '..', 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ASSIGNMENT_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'assignments')
    ASSIGNMENT_ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'zip'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
