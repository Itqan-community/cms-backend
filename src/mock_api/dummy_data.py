"""
Dummy data for the mock API
"""

from datetime import datetime, timezone

DUMMY_USERS = [
    {
        "id": 1,
        "email": "ahmed.hassan@example.com",
        "name": "Ahmed Hassan",
        "first_name": "Ahmed",
        "last_name": "Hassan",
        "phone_number": "+201234567890",
        "title": "Senior Software Engineer",
        "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face",
        "bio": "Developer interested in Quranic datasets and Islamic studies",
        "organization": "Tech Solutions Inc",
        "location": "Cairo, Egypt",
        "website": "https://ahmeddev.com",
        "github_username": "ahmeddev",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "email"
    },
    {
        "id": 2,
        "email": "fatima.ali@example.com",
        "name": "Fatima Ali",
        "first_name": "Fatima",
        "last_name": "Ali",
        "phone_number": "+966501234567",
        "title": "Islamic Studies Researcher",
        "avatar_url": "https://images.unsplash.com/photo-1494790108755-2616b612b647?w=150&h=150&fit=crop&crop=face",
        "bio": "Islamic scholar and content researcher",
        "organization": "Islamic Research Center",
        "location": "Medina, Saudi Arabia",
        "website": "https://research.islamic.edu",
        "github_username": "fatima_research",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "google"
    },
    {
        "id": 3,
        "email": "omar.ibrahim@example.com",
        "name": "Omar Ibrahim",
        "first_name": "Omar",
        "last_name": "Ibrahim",
        "phone_number": "+966511234567",
        "title": "Software Engineer & Quran Teacher",
        "avatar_url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop&crop=face",
        "bio": "Software engineer and Quran memorization teacher",
        "organization": "Digital Quran Academy",
        "location": "Riyadh, Saudi Arabia",
        "website": "https://omardev.io",
        "github_username": "omar-ibrahim",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "github"
    },
    {
        "id": 4,
        "email": "aisha.mohamed@example.com",
        "name": "Aisha Mohamed",
        "avatar_url": "https://images.unsplash.com/photo-1489424731084-a5d8b219a5bb?w=150&h=150&fit=crop&crop=face",
        "bio": "Islamic studies researcher and Arabic language teacher",
        "organization": "University of Al-Azhar",
        "location": "Cairo, Egypt",
        "website": "https://aisha-research.edu",
        "github_username": "aisha_academia",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "email"
    },
    {
        "id": 5,
        "email": "yusuf.khan@example.com",
        "name": "Yusuf Khan",
        "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&h=150&fit=crop&crop=face",
        "bio": "Data scientist working on Quranic text analysis and NLP",
        "organization": "Islamic AI Research Lab",
        "location": "Islamabad, Pakistan",
        "website": "https://yusufkhan.dev",
        "github_username": "yusuf-khan-nlp",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "google"
    },
    {
        "id": 6,
        "email": "mariam.zahid@example.com",
        "name": "Mariam Zahid",
        "avatar_url": "https://images.unsplash.com/photo-1544725176-7c40e5a71c5e?w=150&h=150&fit=crop&crop=face",
        "bio": "Frontend developer building Islamic educational apps",
        "organization": "Muslim Tech Collective",
        "location": "London, UK",
        "website": "https://mariam.codes",
        "github_username": "mariam-zahid",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "github"
    },
    {
        "id": 7,
        "email": "test@example.com",
        "name": "Test User",
        "avatar_url": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&h=150&fit=crop&crop=face",
        "bio": "Test account for development and debugging",
        "organization": "Test Organization",
        "location": "Test City",
        "website": "https://test.example.com",
        "github_username": "testuser",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "email"
    },
    {
        "id": 8,
        "email": "admin@example.com",
        "name": "Admin User",
        "avatar_url": "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150&h=150&fit=crop&crop=face",
        "bio": "System administrator with full access",
        "organization": "Itqan CMS",
        "location": "Global",
        "website": "https://admin.itqan.dev",
        "github_username": "itqan-admin",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "email"
    },
    {
        "id": 9,
        "email": "developer@github.com",
        "name": "GitHub Developer",
        "avatar_url": "https://images.unsplash.com/photo-1556157382-97eda2d62296?w=150&h=150&fit=crop&crop=face",
        "bio": "Open source contributor focused on Islamic software projects",
        "organization": "GitHub",
        "location": "San Francisco, CA",
        "website": "https://github.com/muslim-dev",
        "github_username": "muslim-dev",
        "email_verified": True,
        "profile_completed": True,
        "auth_provider": "github"
    }
]

# Test credentials for easy login testing
TEST_CREDENTIALS = [
    {"email": "ahmed.hassan@example.com", "password": "password123"},
    {"email": "fatima.ali@example.com", "password": "securepass456"},
    {"email": "omar.ibrahim@example.com", "password": "github789"},
    {"email": "aisha.mohamed@example.com", "password": "research2024"},
    {"email": "yusuf.khan@example.com", "password": "datascience"},
    {"email": "mariam.zahid@example.com", "password": "frontend2024"},
    {"email": "test@example.com", "password": "test"},
    {"email": "admin@example.com", "password": "admin123"},
    {"email": "developer@github.com", "password": "opensource"}
]

DUMMY_LICENSES = [
    {
        "code": "cc0",
        "name": "CC0 - Public Domain",
        "short_name": "CC0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/cc-zero.svg",
        "summary": "The person who associated a work with this deed has dedicated the work to the public domain by waiving all of his or her rights to the work worldwide under copyright law.",
        "full_text": "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication...",
        "legal_code_url": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
        "license_terms": [
            {"title": "Freedom", "description": "The work is free for any use", "order": 1}
        ],
        "permissions": [
            {"key": "commercial-use", "label": "Commercial use", "description": "This work may be used for commercial purposes"},
            {"key": "modification", "label": "Modification", "description": "This work may be modified"},
            {"key": "distribution", "label": "Distribution", "description": "This work may be distributed"}
        ],
        "conditions": [],
        "limitations": [],
        "usage_count": 45,
        "is_default": True
    },
    {
        "code": "cc-by-4.0",
        "name": "Creative Commons Attribution 4.0 International",
        "short_name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by.svg",
        "summary": "This license allows reusers to distribute, remix, adapt, and build upon the material in any medium or format, so long as attribution is given to the creator.",
        "full_text": "Creative Commons Attribution 4.0 International License...",
        "legal_code_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
        "license_terms": [
            {"title": "Attribution", "description": "You must give appropriate credit", "order": 1}
        ],
        "permissions": [
            {"key": "commercial-use", "label": "Commercial use", "description": "This work may be used for commercial purposes"},
            {"key": "modification", "label": "Modification", "description": "This work may be modified"},
            {"key": "distribution", "label": "Distribution", "description": "This work may be distributed"}
        ],
        "conditions": [
            {"key": "include-copyright", "label": "Include copyright", "description": "Include original copyright notice"}
        ],
        "limitations": [
            {"key": "trademark-use", "label": "Trademark use", "description": "This license does not grant trademark rights"}
        ],
        "usage_count": 23,
        "is_default": False
    }
]

DUMMY_PUBLISHERS = [
    {
        "id": 1,
        "name": "Tafsir Center",
        "description": "Leading center for Quranic commentary and interpretation",
        "bio": "The Tafsir Center has been dedicated to producing high-quality Quranic commentary and interpretation resources for over 20 years.",
        "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=200&h=200&fit=crop",
        "cover_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=800&h=300&fit=crop",
        "location": "Mecca, Saudi Arabia",
        "website": "https://tafsircenter.org",
        "verified": True,
        "social_links": {
            "twitter": "tafsircenter",
            "github": "tafsir-center"
        },
        "stats": {
            "resources_count": 12,
            "assets_count": 45,
            "total_downloads": 15847,
            "joined_at": "2020-03-15T10:30:00Z"
        }
    },
    {
        "id": 2,
        "name": "Quranic Audio Foundation",
        "description": "Preserving and distributing authentic Quranic recitations",
        "bio": "We collect, preserve, and distribute high-quality audio recordings of Quranic recitations from renowned scholars and reciters.",
        "thumbnail_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=200&h=200&fit=crop",
        "cover_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=800&h=300&fit=crop",
        "location": "Cairo, Egypt",
        "website": "https://quranicaudio.org",
        "verified": True,
        "social_links": {
            "twitter": "quranicaudio",
            "github": "quranic-audio"
        },
        "stats": {
            "resources_count": 8,
            "assets_count": 32,
            "total_downloads": 9234,
            "joined_at": "2021-07-22T14:20:00Z"
        }
    }
]

DUMMY_ASSETS = [
    {
        "id": 1,
        "title": "Quran Uthmani Script",
        "description": "Complete Quran in Uthmani script with diacritics",
        "long_description": "This comprehensive dataset contains the complete Quran text in the traditional Uthmani script, including full diacritical marks (harakat) and proper verse divisions. The text follows the Medina Mushaf standard and has been carefully reviewed by Islamic scholars.",
        "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=300&h=200&fit=crop",
        "category": "mushaf",
        "license": {
            "code": "cc0",
            "name": "CC0 - Public Domain",
            "short_name": "CC0",
            "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/cc-zero.svg",
            "is_default": True
        },
        "snapshots": [
            {
                "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=300&h=200&fit=crop",
                "title": "Uthmani Script Sample",
                "description": "Sample page showing Arabic calligraphy"
            }
        ],
        "publisher": {
            "id": 1,
            "name": "Tafsir Center",
            "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=200&h=200&fit=crop",
            "bio": "Leading center for Quranic commentary",
            "verified": True
        },
        "resource": {
            "id": 1,
            "title": "Complete Quran Dataset v2.1",
            "description": "Comprehensive Quranic text collection"
        },
        "technical_details": {
            "file_size": "2.5 MB",
            "format": "UTF-8 Text",
            "encoding": "UTF-8",
            "version": "2.1",
            "language": "Arabic"
        },
        "stats": {
            "download_count": 1250,
            "view_count": 5847,
            "created_at": "2024-01-15T08:30:00Z",
            "updated_at": "2024-01-20T14:45:00Z"
        },
        "access": {
            "has_access": False,
            "requires_approval": False
        },
        "related_assets": [
            {
                "id": 2,
                "title": "Quran Simple Script",
                "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=150&h=100&fit=crop"
            }
        ],
        "has_access": False,
        "download_count": 1250,
        "file_size": "2.5 MB"
    },
    {
        "id": 2,
        "title": "Quran Simple Script",
        "description": "Simplified Quran text without diacritics for easy reading",
        "long_description": "This version of the Quran text uses simplified Arabic script without diacritical marks, making it easier to read for beginners and those learning Arabic. The text maintains proper verse divisions and chapter organization.",
        "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=300&h=200&fit=crop",
        "category": "mushaf",
        "license": {
            "code": "cc0",
            "name": "CC0 - Public Domain",
            "short_name": "CC0",
            "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/cc-zero.svg",
            "is_default": True
        },
        "snapshots": [
            {
                "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=300&h=200&fit=crop",
                "title": "Simple Script Sample",
                "description": "Clean, easy-to-read Arabic text"
            }
        ],
        "publisher": {
            "id": 1,
            "name": "Tafsir Center",
            "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=200&h=200&fit=crop",
            "bio": "Leading center for Quranic commentary",
            "verified": True
        },
        "resource": {
            "id": 1,
            "title": "Complete Quran Dataset v2.1",
            "description": "Comprehensive Quranic text collection"
        },
        "technical_details": {
            "file_size": "1.8 MB",
            "format": "UTF-8 Text",
            "encoding": "UTF-8",
            "version": "2.1",
            "language": "Arabic"
        },
        "stats": {
            "download_count": 892,
            "view_count": 3421,
            "created_at": "2024-01-15T08:30:00Z",
            "updated_at": "2024-01-20T14:45:00Z"
        },
        "access": {
            "has_access": True,
            "requires_approval": False
        },
        "related_assets": [
            {
                "id": 1,
                "title": "Quran Uthmani Script",
                "thumbnail_url": "https://images.unsplash.com/photo-1585036156171-384164a8c675?w=150&h=100&fit=crop"
            }
        ],
        "has_access": True,
        "download_count": 892,
        "file_size": "1.8 MB"
    },
    {
        "id": 3,
        "title": "Tafsir Ibn Kathir - English",
        "description": "Complete English translation of Tafsir Ibn Kathir",
        "long_description": "The renowned commentary of the Quran by Ibn Kathir, translated into English. This comprehensive work provides detailed explanations of Quranic verses, historical context, and scholarly interpretations that have guided Muslims for centuries.",
        "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=300&h=200&fit=crop",
        "category": "tafsir",
        "license": {
            "code": "cc-by-4.0",
            "name": "Creative Commons Attribution 4.0 International",
            "short_name": "CC BY 4.0",
            "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by.svg",
            "is_default": False
        },
        "snapshots": [
            {
                "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=300&h=200&fit=crop",
                "title": "Tafsir Sample Page",
                "description": "English commentary with Arabic references"
            }
        ],
        "publisher": {
            "id": 1,
            "name": "Tafsir Center",
            "thumbnail_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=200&h=200&fit=crop",
            "bio": "Leading center for Quranic commentary",
            "verified": True
        },
        "resource": {
            "id": 2,
            "title": "Classical Tafsir Collection",
            "description": "Authoritative commentary texts"
        },
        "technical_details": {
            "file_size": "15.2 MB",
            "format": "PDF",
            "encoding": "UTF-8",
            "version": "1.0",
            "language": "English"
        },
        "stats": {
            "download_count": 2341,
            "view_count": 8765,
            "created_at": "2024-01-10T12:15:00Z",
            "updated_at": "2024-01-18T09:20:00Z"
        },
        "access": {
            "has_access": False,
            "requires_approval": True
        },
        "related_assets": [],
        "has_access": False,
        "download_count": 2341,
        "file_size": "15.2 MB"
    },
    {
        "id": 4,
        "title": "Sheikh Sudais Recitation - Al-Fatiha",
        "description": "Beautiful recitation of Surah Al-Fatiha by Sheikh Abdul Rahman Al-Sudais",
        "long_description": "High-quality audio recording of Surah Al-Fatiha recited by Sheikh Abdul Rahman Al-Sudais, former Imam of the Grand Mosque in Mecca. This recording captures the melodious and precise recitation style that has made Sheikh Sudais one of the most beloved Quran reciters worldwide.",
        "thumbnail_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=300&h=200&fit=crop",
        "category": "recitation",
        "license": {
            "code": "cc0",
            "name": "CC0 - Public Domain",
            "short_name": "CC0",
            "icon_url": "https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/cc-zero.svg",
            "is_default": True
        },
        "snapshots": [
            {
                "thumbnail_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=300&h=200&fit=crop",
                "title": "Audio Waveform",
                "description": "Visual representation of the recitation"
            }
        ],
        "publisher": {
            "id": 2,
            "name": "Quranic Audio Foundation",
            "thumbnail_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?w=200&h=200&fit=crop",
            "bio": "Preserving authentic Quranic recitations",
            "verified": True
        },
        "resource": {
            "id": 3,
            "title": "Sheikh Sudais Complete Recitation",
            "description": "Full Quran recitation collection"
        },
        "technical_details": {
            "file_size": "3.1 MB",
            "format": "MP3",
            "encoding": "320kbps",
            "version": "1.0",
            "language": "Arabic"
        },
        "stats": {
            "download_count": 5629,
            "view_count": 12384,
            "created_at": "2024-01-05T16:45:00Z",
            "updated_at": "2024-01-12T11:30:00Z"
        },
        "access": {
            "has_access": True,
            "requires_approval": False
        },
        "related_assets": [],
        "has_access": True,
        "download_count": 5629,
        "file_size": "3.1 MB"
    }
]

CONTENT_STANDARDS = {
    "version": "1.2.0",
    "last_updated": "2024-01-25T10:00:00Z",
    "sections": [
        {
            "title": "Text Standards",
            "content": "All Quranic text must follow established Uthmani script standards with proper diacritical marks.",
            "subsections": [
                {
                    "title": "Character Encoding",
                    "content": "UTF-8 encoding is required for all text files to ensure proper display of Arabic characters."
                },
                {
                    "title": "Verse Numbering",
                    "content": "Verses must be numbered according to the standard Medina Mushaf system."
                }
            ],
            "required_fields": ["text_encoding", "verse_numbers", "chapter_divisions"],
            "default_license": "cc0"
        },
        {
            "title": "Audio Standards",
            "content": "Audio files must meet specific quality and format requirements for optimal user experience.",
            "subsections": [
                {
                    "title": "Quality Requirements",
                    "content": "Minimum 192kbps bitrate with clear pronunciation and minimal background noise."
                },
                {
                    "title": "Format Specifications",
                    "content": "MP3 or FLAC formats are preferred for broad compatibility."
                }
            ],
            "required_fields": ["bitrate", "format", "duration"],
            "default_license": "cc-by-4.0"
        }
    ],
    "file_formats": {
        "supported": ["txt", "pdf", "mp3", "flac", "json", "xml"],
        "recommended": ["txt", "pdf", "mp3"],
        "specifications": {
            "txt": {
                "schema_url": "https://schemas.itqan.dev/text/v1.0/schema.json",
                "example_url": "https://examples.itqan.dev/text/sample.txt"
            },
            "mp3": {
                "schema_url": "https://schemas.itqan.dev/audio/v1.0/schema.json",
                "example_url": "https://examples.itqan.dev/audio/sample.mp3"
            }
        }
    }
}

APP_CONFIG = {
    "version": "1.0.0",
    "features": {
        "auto_approve_access": True,
        "manual_license_review": False,
        "advanced_analytics": False,
        "api_access": False
    },
    "limits": {
        "max_file_size_mb": 100,
        "max_files_per_resource": 10,
        "max_resources_per_publisher": 50
    },
    "ui": {
        "primary_color": "#669B80",
        "dark_color": "#22433D",
        "supported_locales": ["en", "ar"],
        "default_locale": "en"
    },
    "categories": [
        {
            "key": "mushaf",
            "name": "Mushaf",
            "description": "Complete Quran text and manuscripts"
        },
        {
            "key": "tafsir",
            "name": "Tafsir",
            "description": "Quranic commentary and interpretation"
        },
        {
            "key": "recitation",
            "name": "Recitation",
            "description": "Audio recordings of Quranic recitation"
        }
    ],
    "external_links": {
        "docs": "https://docs.itqan.dev",
        "support": "https://support.itqan.dev",
        "github": "https://github.com/itqan-dev"
    }
}
