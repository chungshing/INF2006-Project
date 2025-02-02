from flask import Flask, render_template, request, redirect, url_for, abort

app = Flask(__name__)

# In-memory polls storage.
# Each poll will also have a "results" field: a list of lists
# Each inner list contains vote counts for each option in that question.
polls = [
    {
        'id': 1,
        'title': 'Favorite Programming Language',
        'description': 'Vote on your favorite programming language.',
        'questions': [
            {
                'question': 'Which language do you prefer?',
                'options': ['Python', 'JavaScript', 'Java', 'C++']
            }
        ],
        'results': [[0, 0, 0, 0]]
    }
]


@app.route('/')
def index():
    return render_template('index.html', polls=polls)


@app.route('/create_poll', methods=['GET', 'POST'])
def create_poll():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        questions = []
        index = 0
        while True:
            question_text = request.form.get(f'questions[{index}][question]')
            if question_text is None:
                break
            options = request.form.getlist(f'questions[{index}][options][]')
            options = [opt for opt in options if opt.strip() != ""]
            questions.append({
                'question': question_text,
                'options': options
            })
            index += 1

        # Initialize results for each question with zeros.
        results = []
        for q in questions:
            results.append([0] * len(q['options']))

        new_poll = {
            'id': len(polls) + 1,
            'title': title,
            'description': description,
            'questions': questions,
            'results': results
        }
        polls.append(new_poll)
        return redirect(url_for('index'))

    return render_template('create_poll.html')


@app.route('/edit_poll/<int:poll_id>', methods=['GET', 'POST'])
def edit_poll(poll_id):
    poll = next((p for p in polls if p['id'] == poll_id), None)
    if not poll:
        abort(404)
    if request.method == 'POST':
        poll['title'] = request.form.get('title')
        poll['description'] = request.form.get('description')
        questions = []
        index = 0
        while True:
            question_text = request.form.get(f'questions[{index}][question]')
            if question_text is None:
                break
            options = request.form.getlist(f'questions[{index}][options][]')
            options = [opt for opt in options if opt.strip() != ""]
            questions.append({
                'question': question_text,
                'options': options
            })
            index += 1
        poll['questions'] = questions
        # For simplicity, we reset the results when editing.
        results = []
        for q in questions:
            results.append([0] * len(q['options']))
        poll['results'] = results
        return redirect(url_for('index'))
    return render_template('edit_poll.html', poll=poll)


# New route: Delete a poll
@app.route('/delete_poll/<int:poll_id>', methods=['POST'])
def delete_poll(poll_id):
    global polls
    polls[:] = [p for p in polls if p['id'] != poll_id]
    return redirect(url_for('index'))


# Route for voting on a poll.
# GET displays the voting form; POST records the votes.
@app.route('/poll/<int:poll_id>', methods=['GET', 'POST'])
def view_poll(poll_id):
    poll = next((p for p in polls if p['id'] == poll_id), None)
    if not poll:
        abort(404)
    if request.method == 'POST':
        # For each question, record the vote
        for i, question in enumerate(poll['questions']):
            # The radio group name is "question{i}"
            selected = request.form.get(f'question{i}')
            if selected is not None:
                try:
                    option_index = int(selected)
                    poll['results'][i][option_index] += 1
                except ValueError:
                    pass
        return redirect(url_for('poll_results', poll_id=poll_id))
    # GET: display the voting form.
    return render_template('poll_vote.html', poll=poll)


# Route for viewing poll results.
@app.route('/poll/<int:poll_id>/results')
def poll_results(poll_id):
    poll = next((p for p in polls if p['id'] == poll_id), None)
    if not poll:
        abort(404)
    return render_template('poll_results.html', poll=poll)


if __name__ == '__main__':
    app.run(debug=True)
