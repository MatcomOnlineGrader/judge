import os
import json

from django.conf import settings


def get_extension(folder):
    if folder == 'inputs' or folder == 'sample inputs':
        return 'in'
    if folder == 'outputs' or folder == 'sample outputs':
        return 'out'
    return ''


def parse_samples_json(text):
    try:
        result = json.loads(text)
    except:
        result = dict()
    for file_name in result.keys():
        if not isinstance(result[file_name], dict):
            result[file_name] = dict()
        if 'in' not in result[file_name]:
            result[file_name]['in'] = ''
        if 'out' not in result[file_name]:
            result[file_name]['out'] = ''
    return result


def get_tests(problem, folder):
    """get the name of the sample files"""
    if folder in ['inputs', 'outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))

    if folder in ['sample inputs', 'sample outputs']:
        samples = parse_samples_json(problem.samples)
        ext = get_extension(folder)
        return sorted([name + '.' + ext for name in samples.keys() if len(samples[name][ext]) > 0])

    return []


def handle_tests(problem, files, folder):
    """copy files into an specified problem folder"""
    fix_problem_folder(problem)
    if folder in ['inputs', 'outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return
        for incoming_file in files:
            name = incoming_file.name.replace(' ', '_')  # grader issues
            with open(os.path.join(path, name), 'wb+') as f:
                for chunk in incoming_file.chunks():
                    f.write(chunk)
            incoming_file.close()

    if folder in ['sample inputs', 'sample outputs']:
        samples_json = parse_samples_json(problem.samples)
        for incoming_file in files:
            content = ''
            name = incoming_file.name.replace(' ', '_').split('.')[0]
            for chunk in incoming_file.chunks():
                content += chunk.decode("utf-8")
            ext = get_extension(folder)
            if name not in samples_json:
                samples_json[name] = dict()
            samples_json[name][ext] = content
        problem.samples = json.dumps(samples_json)
        problem.save()


def handle_remove_test(problem, folder, test):
    if folder in ['inputs', 'outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        try:
            os.remove(path)
            return True
        except OSError:
            pass

    if folder in ['sample inputs', 'sample outputs']:
        name = test.split('.')[0]
        ext = get_extension(folder)
        samples_json = parse_samples_json(problem.samples)
        if name in samples_json:
            samples_json[name][ext] = ''
            problem.samples = json.dumps(samples_json)
            problem.save()
            return True
    return False


def test_content(problem, folder, test):
    if folder in ['inputs', 'outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = ''.join(f.readlines())
            return content

    if folder in ['sample inputs', 'sample outputs']:
        samples_json = parse_samples_json(problem.samples)
        ext = get_extension(folder)
        test_name = test.split('.')[0]
        if test_name not in samples_json:
            return None
        return samples_json[test_name][ext]

    return None


def write_to_test(problem, folder, test, content):
    if folder in ['inputs', 'outputs']:
        if handle_remove_test(problem, folder, test):
            path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
            with open(path, 'w') as f:
                f.write(content)

    if folder in ['sample inputs', 'sample outputs']:
        samples_json = parse_samples_json(problem.samples)
        ext = get_extension(folder)
        test_name = test.split('.')[0]
        if test_name in samples_json:
            samples_json[test_name][ext] = content
            problem.samples = json.dumps(samples_json)
            problem.save()


def fix_problem_folder(problem):
    folders = [
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id)),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'outputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample outputs'),
    ]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)