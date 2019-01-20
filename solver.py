import argparse
from recaptcha_solver import RecaptchaSolver
from url_reformat import reformat_url

def main():
    url = 'https://www.google.com/recaptcha/api2/demo'
    parser = argparse.ArgumentParser(description='Options to pass in to the solver')
    parser.add_argument('-url', nargs=1, type=str, help='URL that contains the captcha')
    parser.add_argument('--save', action='store_true', help='Save captcha images for training purposes')
    args = parser.parse_args()

    url = reformat_url(args.url.pop()) if args.url is not None else url
    print("Solving reCAPTCHA for site: " + url)
    solver = RecaptchaSolver(url)
    solver.solve_recaptcha(args.save)

if __name__ == '__main__':
    main()