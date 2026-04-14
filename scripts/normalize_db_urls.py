#!/usr/bin/env python3
"""Normalize stored upload URLs in the DB.

Rewrites absolute URLs that point to localhost (or contain a full
uploads path) into a relative `/api/uploads/...` path so the frontend
served over HTTPS will load assets from the production API host.

Usage (on server/PythonAnywhere):
  cd ~/backendportofoliorani
  source ~/venv/pa-venv/bin/activate   # if you use a virtualenv
  python3 scripts/normalize_db_urls.py

The script will try to back up the local sqlite DB file if it exists.
"""
import os
import sys
import shutil
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    # already a relative uploads path
    if url.startswith('/api/uploads/'):
        return url

    # contains uploads path somewhere
    idx = url.find('/api/uploads/')
    if idx != -1:
        return url[idx:]

    # try parsing and using the path
    try:
        p = urlparse(url)
        path = p.path or ''
        if path.startswith('/api/uploads/'):
            return path
    except Exception:
        pass

    return url


def backup_sqlite(backend_root: str):
    db_file = os.path.join(backend_root, 'portfolio.db')
    if os.path.exists(db_file):
        bak = db_file + '.bak'
        shutil.copy2(db_file, bak)
        print(f'Backup created: {bak}')


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(script_dir)

    # ensure we can import app.py
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    try:
        from app import app, db, HeroSection, AboutSection, PortfolioItem, Testimonial
    except Exception as e:
        print('Failed to import app and models:', e)
        sys.exit(1)

    print('Starting DB URL normalization...')
    backup_sqlite(backend_root)

    changes = []
    with app.app_context():
        # HeroSection
        hero = HeroSection.query.first()
        if hero:
            for field in ('photo_url', 'cv_url'):
                v = getattr(hero, field)
                nv = normalize_url(v)
                if nv != v:
                    setattr(hero, field, nv)
                    changes.append(f'Hero.{field}: {v} -> {nv}')

        # AboutSection
        about = AboutSection.query.first()
        if about:
            v = about.photo_url
            nv = normalize_url(v)
            if nv != v:
                about.photo_url = nv
                changes.append(f'About.photo_url: {v} -> {nv}')

        # Portfolio items
        for p in PortfolioItem.query.all():
            for field in ('url', 'thumbnail_url'):
                v = getattr(p, field)
                nv = normalize_url(v)
                if nv != v:
                    setattr(p, field, nv)
                    changes.append(f'PortfolioItem[{p.id}].{field}: {v} -> {nv}')

        # Testimonials
        for t in Testimonial.query.all():
            v = t.photo_url
            nv = normalize_url(v)
            if nv != v:
                t.photo_url = nv
                changes.append(f'Testimonial[{t.id}].photo_url: {v} -> {nv}')

        if changes:
            db.session.commit()
            print('Applied changes:')
            for c in changes:
                print(' -', c)
        else:
            print('No URL changes needed.')


if __name__ == '__main__':
    main()
