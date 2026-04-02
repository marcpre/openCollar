import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the minimal chat shell', async () => {
    render(<App />);

    expect(await screen.findByText('Desktop agent chat')).toBeInTheDocument();
    expect(await screen.findByPlaceholderText('Describe the task for the desktop agent.')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open settings' })).toBeInTheDocument();
  });
});
