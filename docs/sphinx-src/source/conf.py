# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys


# Insert the parent dir so that "roy-scripts" is on sys.path
sys.path.insert(0, os.path.abspath('/Users/madisonrichardson/Roy/roy-scripts'))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = 'Roy Scripts API'
copyright = '2025, Roy Mendelssohn & Madison Richardson'
author = 'Roy Mendelssohn & Madison Richardson'
release = '0.1'


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration


extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode', 'sphinx.ext.napoleon']

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'

# 5. Now that RTD is the theme, extra_nav_links is valid
html_theme_options = {
    "navigation_depth":    4,
    "collapse_navigation": False,
}

html_static_path = ['_static']

# Tell Sphinx to copy "_static/custom.css" into each HTML page
html_css_files = [
    'custom.css',
]

# This HTML will be inserted at the very top of every generated page:
rst_prolog = """
.. raw:: html

   <a href="../index.html" class="backlink">← Back to Quarto Home</a>
"""
