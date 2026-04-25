import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App UI', () => {
  it('renders the dashboard by default', () => {
    render(<App />);

    expect(screen.getByText(/Weekly Dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Onboarding \+ Profiling Agent/i)).toBeInTheDocument();
  });

  it('navigates between primary tabs', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', {name: /Contacts/i}));
    expect(screen.getByText(/Household Members/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', {name: /Profile/i}));
    expect(screen.getByText(/Profile Settings/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', {name: /Alfred/i}));
    expect(screen.getByText(/Always at your service/i)).toBeInTheDocument();
  });

  it('provides chat controls that users can interact with', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', {name: /Alfred/i}));

    const messageInput = screen.getByPlaceholderText(/Type a message/i);
    await user.type(messageInput, 'Test message');

    expect(messageInput).toHaveValue('Test message');
    expect(screen.getAllByRole('button')).not.toHaveLength(0);
  });
});
