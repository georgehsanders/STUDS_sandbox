"""Help & tutorials blueprint.

Self-contained module — owns its own templates and static assets so adding
new tutorials is a matter of dropping new content into TUTORIALS plus a new
template, with no edits to the rest of the app.
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

help_bp = Blueprint(
    'help',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static',
    url_prefix='/help',
)


# Tutorial registry — append new entries here and add a corresponding step
# template under help/templates/help/.
TUTORIALS = [
    {
        'slug': 'zebra-label-setup',
        'title': 'Zebra Label Template Setup',
        'description': (
            'Step-by-step walkthrough for uploading new data files and '
            're-mapping label templates in the Zebra ZSB Portal.'
        ),
        'endpoint': 'help.zebra_label_setup',
    },
]


# Step content for the Zebra tutorial. Pages refer to filenames in
# help/static/ rendered by render_pdf.py.
ZEBRA_STEPS = [
    {
        'index': 0,
        'heading': 'Step 0: Login to Zebra',
        'pages': [],
    },
    {
        'index': 1,
        'heading': 'Step 1: Delete your old Zebra files',
        'pages': ['page_01.png', 'page_02.png'],
    },
    {
        'index': 2,
        'heading': 'Step 2: Upload new data files',
        'pages': ['page_03.png', 'page_04.png'],
    },
    {
        'index': 3,
        'heading': 'Step 3: Connect your new Zebra files to your Zebra templates',
        'pages': ['page_04.png', 'page_05.png', 'page_06.png', 'page_07.png'],
    },
    {
        'index': 4,
        'heading': 'Step 4: Map your template fields to your data file',
        'pages': ['page_08.png', 'page_09.png', 'page_10.png', 'page_11.png'],
    },
    {
        'index': 5,
        'heading': 'Step 5: Review and lock your changes',
        'pages': ['page_12.png'],
    },
]
TOTAL_STEPS = len(ZEBRA_STEPS)


@help_bp.route('/')
def index():
    return render_template('help/index.html', tutorials=TUTORIALS)


@help_bp.route('/zebra-label-setup')
def zebra_label_setup():
    try:
        step = int(request.args.get('step', 0))
    except (TypeError, ValueError):
        step = 0
    if step < 0 or step >= TOTAL_STEPS:
        return redirect(url_for('help.zebra_label_setup', step=0))

    progress_pct = int(round((step / (TOTAL_STEPS - 1)) * 100)) if TOTAL_STEPS > 1 else 100

    return render_template(
        'help/tutorial.html',
        tutorial_title='Zebra Label Template Setup',
        steps=ZEBRA_STEPS,
        current_step=step,
        total_steps=TOTAL_STEPS,
        progress_pct=progress_pct,
        prev_step=step - 1 if step > 0 else None,
        next_step=step + 1 if step < TOTAL_STEPS - 1 else None,
        is_last=(step == TOTAL_STEPS - 1),
    )
