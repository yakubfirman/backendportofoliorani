import os
import json
import uuid
from datetime import timedelta, datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ─── App Config ────────────────────────────────────────────────────────────────

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "portfolio.db")}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'CHANGE_ME_IN_PRODUCTION_USE_RANDOM_STRING')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}

# Allowed frontend origins for CORS. Set `FRONTEND_URL` env var in PythonAnywhere
# to your frontend domain (can be comma-separated). We include localhost and
# a sensible default for the deployed Vercel app so the site works out-of-the-box.
frontend_env = os.environ.get('FRONTEND_URL', '')
# Allow multiple comma-separated origins from the env var
env_origins = [o.strip() for o in frontend_env.split(',') if o.strip()] if frontend_env else []
FRONTEND_ORIGINS = [
    'http://localhost:3000',
    'https://maharanirizka.vercel.app',
] + env_origins

# Normalized set (strip trailing slash, lowercase) used for tolerant comparisons
FRONTEND_ORIGINS_NORMALIZED = [o.rstrip('/').lower() for o in FRONTEND_ORIGINS if o]

# Log configured frontend origins so it's visible in the PythonAnywhere error log
# This helps confirm which origins the app will allow for CORS in production.
try:
    app.logger.info("FRONTEND_URL env var: %s", frontend_env)
    app.logger.info("Resolved FRONTEND_ORIGINS: %s", FRONTEND_ORIGINS)
except Exception:
    # avoid crashing if logger isn't fully configured yet
    pass

db = SQLAlchemy(app)
jwt = JWTManager(app)
# Configure CORS explicitly for API routes so preflight requests include the
# expected Access-Control headers (especially when `Authorization` header used).
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [o for o in FRONTEND_ORIGINS if o],
            "methods": ["GET", "HEAD", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
    supports_credentials=True,
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.after_request
def _ensure_cors_headers(response):
    """Fallback CORS headers: if the request has an Origin and it's allowed,
    ensure the response (including preflight responses) contains the necessary
    Access-Control-* headers. This is a safe non-wildcard fallback and only
    echoes the origin when it's in the allowed list.
    """
    try:
        origin = request.headers.get('Origin')
        if not origin:
            return response

        # only echo the origin if it's explicitly allowed (tolerant match)
        origin_norm = origin.rstrip('/').lower()
        if origin_norm in FRONTEND_ORIGINS_NORMALIZED:
            # Don't overwrite existing headers set by Flask-CORS, but ensure
            # required headers exist for preflight responses.
            response.headers.setdefault('Access-Control-Allow-Origin', origin)
            response.headers.setdefault('Access-Control-Allow-Credentials', 'true')
            # Vary: Origin so caches differentiate responses
            if 'Vary' in response.headers:
                if 'Origin' not in response.headers['Vary']:
                    response.headers['Vary'] = response.headers['Vary'] + ', Origin'
            else:
                response.headers['Vary'] = 'Origin'
            response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.setdefault('Access-Control-Allow-Methods', 'GET,HEAD,POST,OPTIONS,PUT,PATCH,DELETE')
            # For preflight requests, ensure 200 status
            if request.method == 'OPTIONS':
                response.status_code = 200
    except Exception:
        # never raise from here — logging already exists elsewhere
        pass
    return response


# ─── Models ────────────────────────────────────────────────────────────────────

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class HeroSection(db.Model):
    __tablename__ = 'hero_section'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default='Nama Anda')
    headline = db.Column(db.String(300), nullable=False, default='English Educator & Curriculum Specialist')
    subheadline = db.Column(db.String(500), default='')
    photo_url = db.Column(db.String(500), default='')
    cv_url = db.Column(db.String(500), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'headline': self.headline,
            'subheadline': self.subheadline,
            'photo_url': self.photo_url,
            'cv_url': self.cv_url,
        }


class AboutSection(db.Model):
    __tablename__ = 'about_section'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, default='')
    photo_url = db.Column(db.String(500), default='')

    def to_dict(self):
        return {'id': self.id, 'content': self.content, 'photo_url': self.photo_url}


class Experience(db.Model):
    __tablename__ = 'experiences'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    institution = db.Column(db.String(300), nullable=False)
    exp_type = db.Column(db.String(50), default='formal')  # 'formal' | 'pkl'
    period = db.Column(db.String(100), default='')
    description = db.Column(db.Text, default='')
    responsibilities = db.Column(db.Text, default='[]')  # JSON array
    order_num = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'institution': self.institution,
            'type': self.exp_type,
            'period': self.period,
            'description': self.description,
            'responsibilities': json.loads(self.responsibilities or '[]'),
            'order': self.order_num,
        }


class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='hard')  # 'hard' | 'soft'
    level = db.Column(db.Integer, default=80)
    order_num = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'level': self.level,
            'order': self.order_num,
        }


class PortfolioItem(db.Model):
    __tablename__ = 'portfolio_items'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default='')
    item_type = db.Column(db.String(50), default='document')  # 'document' | 'video' | 'image'
    url = db.Column(db.String(500), default='')
    thumbnail_url = db.Column(db.String(500), default='')
    order_num = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.item_type,
            'url': self.url,
            'thumbnail_url': self.thumbnail_url,
            'order': self.order_num,
        }


class Testimonial(db.Model):
    __tablename__ = 'testimonials'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), default='')
    content = db.Column(db.Text, nullable=False)
    photo_url = db.Column(db.String(500), default='')
    order_num = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'content': self.content,
            'photo_url': self.photo_url,
            'order': self.order_num,
        }


class ContactInfo(db.Model):
    __tablename__ = 'contact_info'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), default='')
    phone = db.Column(db.String(50), default='')
    linkedin_url = db.Column(db.String(500), default='')
    instagram = db.Column(db.String(200), default='')
    address = db.Column(db.String(500), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'linkedin_url': self.linkedin_url,
            'instagram': self.instagram,
            'address': self.address,
        }


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), default='')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subject': self.subject,
            'message': self.message,
            'created_at': self.created_at.isoformat(),
            'is_read': self.is_read,
        }


# ─── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing credentials'}), 400
    user = AdminUser.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    token = create_access_token(identity=user.username)
    return jsonify({'access_token': token, 'username': user.username}), 200


@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def verify():
    return jsonify({'username': get_jwt_identity()}), 200


# ─── Hero Routes ───────────────────────────────────────────────────────────────

@app.route('/api/hero', methods=['GET'])
def get_hero():
    hero = HeroSection.query.first()
    return jsonify(hero.to_dict() if hero else {}), 200



@app.route('/api/hero', methods=['PUT'])
@jwt_required()
def update_hero():
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    hero = HeroSection.query.first()
    if not hero:
        hero = HeroSection()
        db.session.add(hero)
    hero.name = data.get('name', hero.name)
    hero.headline = data.get('headline', hero.headline)
    hero.subheadline = data.get('subheadline', hero.subheadline)

    # Handle photo upload
    if 'photo' in files and allowed_file(files['photo'].filename):
        file = files['photo']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        hero.photo_url = f"/api/uploads/{filename}"
    else:
        hero.photo_url = data.get('photo_url', hero.photo_url)

    # Handle CV upload
    if 'cv' in files and allowed_file(files['cv'].filename):
        file = files['cv']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        hero.cv_url = f"/api/uploads/{filename}"
    else:
        hero.cv_url = data.get('cv_url', hero.cv_url)

    db.session.commit()
    return jsonify(hero.to_dict()), 200


# ─── About Routes ──────────────────────────────────────────────────────────────

@app.route('/api/about', methods=['GET'])
def get_about():
    about = AboutSection.query.first()
    return jsonify(about.to_dict() if about else {}), 200



@app.route('/api/about', methods=['PUT'])
@jwt_required()
def update_about():
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    about = AboutSection.query.first()
    if not about:
        about = AboutSection()
        db.session.add(about)
    about.content = data.get('content', about.content)
    if 'photo' in files and allowed_file(files['photo'].filename):
        file = files['photo']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        about.photo_url = f"/api/uploads/{filename}"
    else:
        about.photo_url = data.get('photo_url', about.photo_url)
    db.session.commit()
    return jsonify(about.to_dict()), 200


# ─── Experience Routes ─────────────────────────────────────────────────────────

@app.route('/api/experiences', methods=['GET'])
def get_experiences():
    exps = Experience.query.order_by(Experience.order_num, Experience.id).all()
    return jsonify([e.to_dict() for e in exps]), 200


@app.route('/api/experiences', methods=['POST'])
@jwt_required()
def create_experience():
    data = request.get_json()
    exp = Experience(
        title=data.get('title', ''),
        institution=data.get('institution', ''),
        exp_type=data.get('type', 'formal'),
        period=data.get('period', ''),
        description=data.get('description', ''),
        responsibilities=json.dumps(data.get('responsibilities', [])),
        order_num=data.get('order', 0),
    )
    db.session.add(exp)
    db.session.commit()
    return jsonify(exp.to_dict()), 201


@app.route('/api/experiences/<int:exp_id>', methods=['PUT'])
@jwt_required()
def update_experience(exp_id):
    exp = db.get_or_404(Experience, exp_id)
    data = request.get_json()
    exp.title = data.get('title', exp.title)
    exp.institution = data.get('institution', exp.institution)
    exp.exp_type = data.get('type', exp.exp_type)
    exp.period = data.get('period', exp.period)
    exp.description = data.get('description', exp.description)
    if 'responsibilities' in data:
        exp.responsibilities = json.dumps(data['responsibilities'])
    exp.order_num = data.get('order', exp.order_num)
    db.session.commit()
    return jsonify(exp.to_dict()), 200


@app.route('/api/experiences/<int:exp_id>', methods=['DELETE'])
@jwt_required()
def delete_experience(exp_id):
    exp = db.get_or_404(Experience, exp_id)
    db.session.delete(exp)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


# ─── Skills Routes ─────────────────────────────────────────────────────────────

@app.route('/api/skills', methods=['GET'])
def get_skills():
    skills = Skill.query.order_by(Skill.category, Skill.order_num, Skill.id).all()
    return jsonify([s.to_dict() for s in skills]), 200


@app.route('/api/skills', methods=['POST'])
@jwt_required()
def create_skill():
    data = request.get_json()
    skill = Skill(
        name=data.get('name', ''),
        category=data.get('category', 'hard'),
        level=data.get('level', 80),
        order_num=data.get('order', 0),
    )
    db.session.add(skill)
    db.session.commit()
    return jsonify(skill.to_dict()), 201


@app.route('/api/skills/<int:skill_id>', methods=['PUT'])
@jwt_required()
def update_skill(skill_id):
    skill = db.get_or_404(Skill, skill_id)
    data = request.get_json()
    skill.name = data.get('name', skill.name)
    skill.category = data.get('category', skill.category)
    skill.level = data.get('level', skill.level)
    skill.order_num = data.get('order', skill.order_num)
    db.session.commit()
    return jsonify(skill.to_dict()), 200


@app.route('/api/skills/<int:skill_id>', methods=['DELETE'])
@jwt_required()
def delete_skill(skill_id):
    skill = db.get_or_404(Skill, skill_id)
    db.session.delete(skill)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


# ─── Portfolio Routes ──────────────────────────────────────────────────────────

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    items = PortfolioItem.query.order_by(PortfolioItem.order_num, PortfolioItem.id).all()
    return jsonify([i.to_dict() for i in items]), 200



@app.route('/api/portfolio', methods=['POST'])
@jwt_required()
def create_portfolio_item():
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    url = data.get('url', '')
    thumbnail_url = data.get('thumbnail_url', '')
    # Handle file upload for url
    if 'file' in files and allowed_file(files['file'].filename):
        file = files['file']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        url = f"/api/uploads/{filename}"
    # Handle thumbnail upload
    if 'thumbnail' in files and allowed_file(files['thumbnail'].filename):
        file = files['thumbnail']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        thumbnail_url = f"/api/uploads/{filename}"
    item = PortfolioItem(
        title=data.get('title', ''),
        description=data.get('description', ''),
        item_type=data.get('type', 'document'),
        url=url,
        thumbnail_url=thumbnail_url,
        order_num=data.get('order', 0),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201



@app.route('/api/portfolio/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_portfolio_item(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    item.title = data.get('title', item.title)
    item.description = data.get('description', item.description)
    item.item_type = data.get('type', item.item_type)
    # Handle file upload for url
    if 'file' in files and allowed_file(files['file'].filename):
        file = files['file']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        item.url = f"/api/uploads/{filename}"
    else:
        item.url = data.get('url', item.url)
    # Handle thumbnail upload
    if 'thumbnail' in files and allowed_file(files['thumbnail'].filename):
        file = files['thumbnail']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        item.thumbnail_url = f"/api/uploads/{filename}"
    else:
        item.thumbnail_url = data.get('thumbnail_url', item.thumbnail_url)
    item.order_num = data.get('order', item.order_num)
    db.session.commit()
    return jsonify(item.to_dict()), 200


@app.route('/api/portfolio/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_portfolio_item(item_id):
    item = db.get_or_404(PortfolioItem, item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


# ─── Testimonials Routes ───────────────────────────────────────────────────────

@app.route('/api/testimonials', methods=['GET'])
def get_testimonials():
    testimonials = Testimonial.query.order_by(Testimonial.order_num, Testimonial.id).all()
    return jsonify([t.to_dict() for t in testimonials]), 200



@app.route('/api/testimonials', methods=['POST'])
@jwt_required()
def create_testimonial():
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    photo_url = data.get('photo_url', '')
    if 'photo' in files and allowed_file(files['photo'].filename):
        file = files['photo']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        photo_url = f"/api/uploads/{filename}"
    t = Testimonial(
        name=data.get('name', ''),
        role=data.get('role', ''),
        content=data.get('content', ''),
        photo_url=photo_url,
        order_num=data.get('order', 0),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201



@app.route('/api/testimonials/<int:t_id>', methods=['PUT'])
@jwt_required()
def update_testimonial(t_id):
    t = db.get_or_404(Testimonial, t_id)
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        data = request.form
        files = request.files
    else:
        data = request.get_json() or {}
        files = {}
    t.name = data.get('name', t.name)
    t.role = data.get('role', t.role)
    t.content = data.get('content', t.content)
    if 'photo' in files and allowed_file(files['photo'].filename):
        file = files['photo']
        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        t.photo_url = f"/api/uploads/{filename}"
    else:
        t.photo_url = data.get('photo_url', t.photo_url)
    t.order_num = data.get('order', t.order_num)
    db.session.commit()
    return jsonify(t.to_dict()), 200


@app.route('/api/testimonials/<int:t_id>', methods=['DELETE'])
@jwt_required()
def delete_testimonial(t_id):
    t = db.get_or_404(Testimonial, t_id)
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


# ─── Contact Info Routes ───────────────────────────────────────────────────────

@app.route('/api/contact-info', methods=['GET'])
def get_contact_info():
    info = ContactInfo.query.first()
    return jsonify(info.to_dict() if info else {}), 200


@app.route('/api/contact-info', methods=['PUT'])
@jwt_required()
def update_contact_info():
    data = request.get_json()
    info = ContactInfo.query.first()
    if not info:
        info = ContactInfo()
        db.session.add(info)
    info.email = data.get('email', info.email)
    info.phone = data.get('phone', info.phone)
    info.linkedin_url = data.get('linkedin_url', info.linkedin_url)
    info.instagram = data.get('instagram', info.instagram)
    info.address = data.get('address', info.address)
    db.session.commit()
    return jsonify(info.to_dict()), 200


# ─── Contact Messages Routes ────────────────────────────────────────────────────

@app.route('/api/contact', methods=['POST'])
def send_message():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email') or not data.get('message'):
        return jsonify({'error': 'Missing required fields: name, email, message'}), 400
    msg = ContactMessage(
        name=data['name'],
        email=data['email'],
        subject=data.get('subject', ''),
        message=data['message'],
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'message': 'Message sent successfully'}), 201


@app.route('/api/messages', methods=['GET'])
@jwt_required()
def get_messages():
        messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
        return jsonify([m.to_dict() for m in messages]), 200


@app.route('/api/messages/<int:msg_id>/read', methods=['PUT'])
@jwt_required()
def mark_message_read(msg_id):
    msg = db.get_or_404(ContactMessage, msg_id)
    msg.is_read = True
    db.session.commit()
    return jsonify(msg.to_dict()), 200


@app.route('/api/messages/<int:msg_id>', methods=['DELETE'])
@jwt_required()
def delete_message(msg_id):
    msg = db.get_or_404(ContactMessage, msg_id)
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200


# ─── File Upload Routes ─────────────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
@jwt_required()
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({'url': f'/api/uploads/{filename}', 'filename': filename}), 201


@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name)


# ─── DB Initialization & Seed ──────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()

        if not AdminUser.query.first():
            admin = AdminUser(username='portorani')
            admin.set_password('porto1122')
            db.session.add(admin)

        if not HeroSection.query.first():
            db.session.add(HeroSection(
                name='Nama Anda',
                headline='English Educator & Curriculum Specialist',
                subheadline='Passionate about empowering students through innovative and communicative English teaching',
                photo_url='',
                cv_url='',
            ))

        if not AboutSection.query.first():
            db.session.add(AboutSection(
                content=(
                    'Saya adalah seorang pendidik bahasa Inggris yang berdedikasi dengan latar belakang '
                    'Pendidikan Bahasa Inggris. Saya percaya bahwa pembelajaran bahasa yang efektif '
                    'dimulai dari pemahaman mendalam tentang konteks budaya dan kebutuhan siswa.\n\n'
                    'Filosofi mengajar saya berpusat pada pendekatan komunikatif yang mengutamakan '
                    'interaksi nyata dan pengembangan kepercayaan diri siswa dalam berbahasa Inggris. '
                    'Visi saya adalah menciptakan lingkungan belajar yang inklusif, menyenangkan, '
                    'dan berdampak nyata bagi masa depan setiap siswa.'
                ),
                photo_url='',
            ))

        if not Experience.query.filter_by(exp_type='formal').first():
            db.session.add(Experience(
                title='Student Teaching Assistant',
                institution='Universitas Pendidikan Indonesia',
                exp_type='formal',
                period='2022 – 2024',
                description='Membantu proses pembelajaran bahasa Inggris di tingkat universitas.',
                responsibilities=json.dumps([
                    'Menyusun RPP dan materi ajar berbasis kurikulum',
                    'Membimbing mahasiswa dalam tugas dan proyek bahasa',
                    'Mengelola platform e-learning dan media digital',
                ]),
                order_num=0,
            ))

        if not Experience.query.filter_by(exp_type='pkl').first():
            db.session.add(Experience(
                title='Guru Praktik PKL',
                institution='SMA Negeri 1 Bandung',
                exp_type='pkl',
                period='Agustus – November 2023',
                description='Pelaksanaan Praktik Kerja Lapangan sebagai guru bahasa Inggris.',
                responsibilities=json.dumps([
                    'Mengajar 30+ siswa per kelas dengan pendekatan komunikatif',
                    'Menyusun silabus dan RPP sesuai Kurikulum Merdeka',
                    'Merancang penilaian formatif dan sumatif',
                    'Berkolaborasi dengan guru pamong dalam evaluasi pembelajaran',
                ]),
                order_num=1,
            ))

        if not Skill.query.first():
            hard_skills = [
                ('TOEFL/IELTS Preparation', 90),
                ('Curriculum Development', 88),
                ('Lesson Planning (RPP)', 92),
                ('Material Development', 85),
                ('English Language Proficiency', 95),
            ]
            soft_skills = [
                ('Public Speaking', 87),
                ('Classroom Management', 90),
                ('Cross-cultural Communication', 85),
                ('Critical Thinking', 83),
                ('Team Collaboration', 88),
            ]
            for i, (name, level) in enumerate(hard_skills):
                db.session.add(Skill(name=name, category='hard', level=level, order_num=i))
            for i, (name, level) in enumerate(soft_skills):
                db.session.add(Skill(name=name, category='soft', level=level, order_num=i))

        if not PortfolioItem.query.first():
            items = [
                ('Silabus Bahasa Inggris Kelas X', 'Silabus lengkap berdasarkan Kurikulum Merdeka untuk kelas X SMA.', 'document'),
                ('RPP Speaking – Descriptive Text', 'Rancangan Pelaksanaan Pembelajaran topik Descriptive Text dengan pendekatan task-based.', 'document'),
                ('Video Demo Mengajar', 'Rekaman kegiatan mengajar langsung di kelas selama PKL.', 'video'),
            ]
            for i, (title, desc, itype) in enumerate(items):
                db.session.add(PortfolioItem(title=title, description=desc, item_type=itype, order_num=i))

        if not Testimonial.query.first():
            testimonials = [
                ('Dr. Hendra Kusuma, M.Pd.', 'Dosen Pembimbing PKL', 'Mahasiswa ini menunjukkan dedikasi luar biasa dalam mempersiapkan materi ajar. Kemampuan komunikasinya sangat baik dan siswa-siswi sangat antusias mengikuti kelasnya.'),
                ('Ibu Sari Rahayu, S.Pd.', 'Guru Pamong SMA Negeri 1 Bandung', 'Selama PKL, beliau berhasil menciptakan suasana belajar yang menyenangkan. RPP yang disusun sangat terstruktur dan sesuai dengan kebutuhan siswa.'),
                ('Budi Santoso', 'Mantan Siswa', 'Cara mengajarnya sangat menarik dan tidak membosankan. Saya jadi lebih percaya diri berbicara dalam bahasa Inggris setelah belajar dengan beliau.'),
            ]
            for i, (name, role, content) in enumerate(testimonials):
                db.session.add(Testimonial(name=name, role=role, content=content, order_num=i))

        if not ContactInfo.query.first():
            db.session.add(ContactInfo(
                email='email@example.com',
                phone='+62 812 3456 7890',
                linkedin_url='https://linkedin.com/in/username',
                instagram='@username',
                address='Bandung, Jawa Barat, Indonesia',
            ))

        db.session.commit()
        print('✅  Database initialized with seed data.')
        print('👤  Default admin  →  username: admin  |  password: admin123')
        print('⚠️   Change the default password after first login!')


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host=host, port=port, debug=debug)
    app.run(debug=True, host='0.0.0.0', port=5000)
